"""Validates US-011: 2h post-date unlock, double-blind submission, 48h timeout reveal, Bayesian smoothing (m=5, C=3.5), and 30-day pair collusion prevention."""

from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import GenderEnum, DatingPreferenceEnum
from src.models.dating import DateInvitation, DateReview, DateStatusEnum, ReviewStatusEnum
from src.core.exceptions import AppErrorCode
from src.services.reputation_service import ReputationService


async def _create_completed_date(
    db_session: AsyncSession,
    user_a,
    user_b,
    conv_id: int,
    completed_at: datetime,
) -> DateInvitation:
    """Helper to set up a completed DateInvitation directly in database."""
    date_inv = DateInvitation(
        conversation_id=conv_id,
        initiator_id=user_a.id,
        recipient_id=user_b.id,
        activity_topic="Dinner",
        scheduled_datetime=completed_at - timedelta(hours=1),
        venue_name="Lakeside Restaurant",
        venue_address="West Lake West Road 1",
        venue_latitude=30.25,
        venue_longitude=120.15,
        status=DateStatusEnum.COMPLETED,
        initiator_checked_in=True,
        recipient_checked_in=True,
        completed_at=completed_at,
        created_at=completed_at - timedelta(days=2),
    )
    db_session.add(date_inv)
    await db_session.commit()
    await db_session.refresh(date_inv)
    return date_inv


@pytest.mark.asyncio
async def test_bayesian_average_computation():
    """NFR-SEC-04 & US-011: Computes Bayesian Average using S = (C * m + sum(ratings)) / (m + v), where m=5, C=3.5."""
    # 0 ratings -> returns baseline C = 3.5
    s0 = ReputationService.calculate_bayesian_score([])
    assert s0 == 3.5

    # 2 ratings: [5.0, 5.0]
    # S = (3.5 * 5 + 10.0) / (5 + 2) = 27.5 / 7 = 3.928... -> 3.93
    s2 = ReputationService.calculate_bayesian_score([5.0, 5.0])
    assert s2 == 3.93

    # 3 ratings: [1.0, 1.0, 1.0]
    # S = (3.5 * 5 + 3.0) / (5 + 3) = 20.5 / 8 = 2.5625 -> 2.56
    s3 = ReputationService.calculate_bayesian_score([1.0, 1.0, 1.0])
    assert s3 == 2.56

    # 10 ratings of 5.0
    # S = (17.5 + 50.0) / 15 = 67.5 / 15 = 4.5
    s10 = ReputationService.calculate_bayesian_score([5.0] * 10)
    assert s10 == 4.5


@pytest.mark.asyncio
async def test_review_unlocked_after_2_hours(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011: Evaluation form unlocks exactly 2 hours after date check-in completion; blocked before."""
    user_a = await test_users_factory(email="reviewer_a@example.com")
    user_b = await test_users_factory(email="reviewee_b@example.com")
    headers_a = auth_headers_factory(user_a)

    now = datetime.utcnow()

    # 1. Date completed only 30 minutes ago (< 2h unlock delay)
    recent_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(minutes=30),
    )

    resp_early = await async_client.post(
        f"/api/v1/reviews/{recent_date.id}",
        headers=headers_a,
        json={
            "rating": 5.0,
            "behavioral_tags": ["Punctual", "Respectful"],
            "comment": "Had a wonderful time!",
        },
    )
    assert resp_early.status_code == 400
    assert resp_early.json()["error_code"] == AppErrorCode.ERR_REVIEW_LOCKED.value

    # 2. Date completed 2.5 hours ago (>= 2h) -> unlocks and succeeds!
    unlocked_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(hours=2, minutes=30),
    )

    resp_ok = await async_client.post(
        f"/api/v1/reviews/{unlocked_date.id}",
        headers=headers_a,
        json={
            "rating": 5.0,
            "behavioral_tags": ["Punctual", "Matches Photos"],
            "comment": "Extremely pleasant date!",
        },
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["date_invitation_id"] == unlocked_date.id
    assert data["status"] == "submitted_blind"
    assert data["is_revealed"] is False


@pytest.mark.asyncio
async def test_double_blind_review_reveal_conditions(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011: Reviews remain blind until BOTH submit OR 48h timeout; upon reveal, Bayesian reputation is recomputed."""
    user_a = await test_users_factory(email="blind_a@example.com", reputation=3.5)
    user_b = await test_users_factory(email="blind_b@example.com", reputation=3.5)
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    completed_time = datetime.utcnow() - timedelta(hours=3)
    date_inv = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=completed_time,
    )

    # 1. User A submits review (5.0 stars)
    resp_a = await async_client.post(
        f"/api/v1/reviews/{date_inv.id}",
        headers=headers_a,
        json={"rating": 5.0, "behavioral_tags": ["Punctual", "Respectful"]},
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["is_revealed"] is False

    # User B queries the reviews before submitting: cannot see User A's rating or tags!
    reviews_for_b = await async_client.get(f"/api/v1/reviews/{date_inv.id}", headers=headers_b)
    for r in reviews_for_b.json():
        if r["reviewer_id"] == user_a.id:
            assert r["rating"] is None
            assert r["behavioral_tags"] is None
            assert r["is_revealed"] is False

    # 2. User B submits review (5.0 stars) -> both have submitted, triggering double-blind reveal!
    resp_b = await async_client.post(
        f"/api/v1/reviews/{date_inv.id}",
        headers=headers_b,
        json={"rating": 5.0, "behavioral_tags": ["Friendly", "Great Conversation"]},
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["is_revealed"] is True

    # Check reviews are now published and visible to both
    published_reviews = (await async_client.get(f"/api/v1/reviews/{date_inv.id}", headers=headers_b)).json()
    assert all(r["is_revealed"] is True for r in published_reviews)
    assert all(r["rating"] is not None for r in published_reviews)

    # Bayesian reputation of User B recomputed: (3.5*5 + 5.0) / 6 = 22.5 / 6 = 3.75
    prof_b = (await async_client.get(f"/api/v1/auth/profile/{user_b.id}")).json()
    assert prof_b["reputation_score"] == 3.75
    # High rating (>= 4.5) awards +30 points to reviewee!
    bal_b = (await async_client.get("/api/v1/points/balance", headers=headers_b)).json()
    assert bal_b["balance"] == 130  # Initial 100 + 30 bonus

    # 3. Test 48-hour auto-reveal timeout when only one party submitted
    user_c = await test_users_factory(email="timeout_c@example.com", reputation=3.5)
    user_d = await test_users_factory(email="timeout_d@example.com", reputation=3.5)
    headers_c = auth_headers_factory(user_c)

    # Date completed 50 hours ago (> 48h)
    old_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_c,
        user_b=user_d,
        conv_id=2,
        completed_at=datetime.utcnow() - timedelta(hours=50),
    )

    # User C submits alone
    sub_c = await async_client.post(
        f"/api/v1/reviews/{old_date.id}",
        headers=headers_c,
        json={"rating": 5.0, "behavioral_tags": ["Polite"]},
    )
    assert sub_c.status_code == 200
    # Because > 48h has passed, it auto-reveals!
    assert sub_c.json()["is_revealed"] is True


@pytest.mark.asyncio
async def test_collusion_prevention_30_day_pair_cooldown(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """NFR-SEC-02 & US-011: Second date between same pair within 30 days is flagged for collusion and excluded from Bayesian calculation."""
    user_a = await test_users_factory(email="pair_a@example.com", reputation=3.5)
    user_b = await test_users_factory(email="pair_b@example.com", reputation=3.5)
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    # Date 1 completed 10 days ago with published reviews
    date1 = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=datetime.utcnow() - timedelta(days=10),
    )
    await async_client.post(f"/api/v1/reviews/{date1.id}", headers=headers_a, json={"rating": 5.0, "behavioral_tags": ["Punctual"]})
    await async_client.post(f"/api/v1/reviews/{date1.id}", headers=headers_b, json={"rating": 5.0, "behavioral_tags": ["Respectful"]})

    # Reputation recomputed for Date 1: 3.75
    prof_b1 = (await async_client.get(f"/api/v1/auth/profile/{user_b.id}")).json()
    assert prof_b1["reputation_score"] == 3.75

    # Date 2 between same pair completed 3 hours ago (within 30-day cooldown)
    date2 = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=datetime.utcnow() - timedelta(hours=3),
    )

    # User A submits review for Date 2
    resp_date2 = await async_client.post(
        f"/api/v1/reviews/{date2.id}",
        headers=headers_a,
        json={"rating": 5.0, "behavioral_tags": ["Punctual"]},
    )
    assert resp_date2.status_code == 200
    data2 = resp_date2.json()
    assert data2["status"] == ReviewStatusEnum.COLLUSION_FLAGGED.value

    # Check that User B's reputation was NOT inflated further by the collusion review
    prof_b2 = (await async_client.get(f"/api/v1/auth/profile/{user_b.id}")).json()
    assert prof_b2["reputation_score"] == 3.75  # Unchanged!


@pytest.mark.asyncio
async def test_review_rating_half_star_increment_validation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011 AC 11.2: Enforces 1.0-5.0 stars with 0.5 increments; invalid steps or out-of-range ratings return 422."""
    user_a = await test_users_factory(email="rate_a@example.com")
    user_b = await test_users_factory(email="rate_b@example.com")
    headers_a = auth_headers_factory(user_a)

    completed_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=datetime.utcnow() - timedelta(hours=3),
    )

    # 1. Invalid step (4.3 stars, not 0.5 step)
    r_step = await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_a,
        json={"rating": 4.3, "behavioral_tags": ["Punctual"]},
    )
    assert r_step.status_code == 422

    # 2. Below minimum (0.5 stars < 1.0)
    r_under = await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_a,
        json={"rating": 0.5, "behavioral_tags": ["Impolite"]},
    )
    assert r_under.status_code == 422

    # 3. Above maximum (5.5 stars > 5.0)
    r_over = await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_a,
        json={"rating": 5.5, "behavioral_tags": ["Great"]},
    )
    assert r_over.status_code == 422


@pytest.mark.asyncio
async def test_review_uncompleted_date_or_non_participant_rejection(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011: Reviews on uncompleted dates return 400 ERR_INVALID_DATE_STATE; non-participants return 403 ERR_AUTH_REQUIRED."""
    user_a = await test_users_factory(email="part_a@example.com")
    user_b = await test_users_factory(email="part_b@example.com")
    user_c = await test_users_factory(email="intruder_reviewer@example.com")
    headers_a = auth_headers_factory(user_a)
    headers_c = auth_headers_factory(user_c)

    # 1. Date is still in confirmed_pending_arrival (not completed)
    date_uncompleted = DateInvitation(
        conversation_id=1,
        initiator_id=user_a.id,
        recipient_id=user_b.id,
        activity_topic="Dinner",
        scheduled_datetime=datetime.utcnow() + timedelta(hours=5),
        venue_name="Restaurant",
        venue_address="Road 1",
        venue_latitude=30.25,
        venue_longitude=120.15,
        status=DateStatusEnum.CONFIRMED_PENDING_ARRIVAL,
        created_at=datetime.utcnow(),
    )
    db_session.add(date_uncompleted)
    await db_session.commit()

    resp_uncompleted = await async_client.post(
        f"/api/v1/reviews/{date_uncompleted.id}",
        headers=headers_a,
        json={"rating": 4.5, "behavioral_tags": ["Punctual"]},
    )
    assert resp_uncompleted.status_code == 400
    assert resp_uncompleted.json()["error_code"] == AppErrorCode.ERR_INVALID_DATE_STATE.value

    # 2. Completed date, but User C is not a participant
    completed_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=datetime.utcnow() - timedelta(hours=3),
    )
    resp_intruder = await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_c,
        json={"rating": 5.0, "behavioral_tags": ["Respectful"]},
    )
    assert resp_intruder.status_code == 403
    assert resp_intruder.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value


@pytest.mark.asyncio
async def test_review_low_rating_no_bonus(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011 AC 11.3 & US-013 AC 13.1: Reviews with rating < 4.5 do not award the +30 high-rating bonus points."""
    user_a = await test_users_factory(email="lowrate_a@example.com")
    user_b = await test_users_factory(email="lowrate_b@example.com", points=100)
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    completed_date = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=datetime.utcnow() - timedelta(hours=3),
    )

    # User A rates User B with 3.5 stars (< 4.5)
    await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_a,
        json={"rating": 3.5, "behavioral_tags": ["Respectful"]},
    )
    # User B rates User A with 3.5 stars -> both submitted, reveals
    await async_client.post(
        f"/api/v1/reviews/{completed_date.id}",
        headers=headers_b,
        json={"rating": 3.5, "behavioral_tags": ["Respectful"]},
    )

    # Check User B's balance remains 100 (no 30 point bonus)
    bal_b = await async_client.get("/api/v1/points/balance", headers=headers_b)
    assert bal_b.json()["balance"] == 100


@pytest.mark.asyncio
async def test_review_unlock_exact_2_hour_boundary(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-011 AC 11.1: Evaluation form unlocks at exactly 2h post check-in (1h 55m locked vs 2h 5m unlocked)."""
    user_a = await test_users_factory(email="unlock_a@example.com")
    user_b = await test_users_factory(email="unlock_b@example.com")
    headers_a = auth_headers_factory(user_a)

    now = datetime.utcnow()

    # 1. Date completed 1h 55m ago (locked)
    date_locked = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(hours=1, minutes=55),
    )
    resp_locked = await async_client.post(
        f"/api/v1/reviews/{date_locked.id}",
        headers=headers_a,
        json={"rating": 4.5, "behavioral_tags": ["Punctual"]},
    )
    assert resp_locked.status_code == 400
    assert resp_locked.json()["error_code"] == AppErrorCode.ERR_REVIEW_LOCKED.value

    # 2. Date completed 2h 5m ago (unlocked)
    date_unlocked = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(hours=2, minutes=5),
    )
    resp_unlocked = await async_client.post(
        f"/api/v1/reviews/{date_unlocked.id}",
        headers=headers_a,
        json={"rating": 4.5, "behavioral_tags": ["Punctual"]},
    )
    assert resp_unlocked.status_code == 200
    assert resp_unlocked.json()["is_revealed"] is False


@pytest.mark.asyncio
async def test_collusion_cooldown_30_day_boundary(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """NFR-SEC-02 & US-011 AC 11.4: 30-day anti-collusion boundary (29 days flagged vs 31 days eligible)."""
    user_a = await test_users_factory(email="cooldown_a@example.com", reputation=3.5)
    user_b = await test_users_factory(email="cooldown_b@example.com", reputation=3.5)
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    now = datetime.utcnow()

    # Date 1 completed 35 days ago
    date1 = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(days=35),
    )
    # Both submit Date 1 -> reveals, User B reputation becomes 3.75
    await async_client.post(f"/api/v1/reviews/{date1.id}", headers=headers_a, json={"rating": 5.0, "behavioral_tags": ["Punctual"]})
    await async_client.post(f"/api/v1/reviews/{date1.id}", headers=headers_b, json={"rating": 5.0, "behavioral_tags": ["Respectful"]})

    prof1 = (await async_client.get(f"/api/v1/auth/profile/{user_b.id}")).json()
    assert prof1["reputation_score"] == 3.75

    # Case 1: Date 2 completed 29 days after Date 1 (6 days ago -> within 30-day cooldown)
    date2 = await _create_completed_date(
        db_session=db_session,
        user_a=user_a,
        user_b=user_b,
        conv_id=1,
        completed_at=now - timedelta(days=6),
    )
    resp2 = await async_client.post(
        f"/api/v1/reviews/{date2.id}",
        headers=headers_a,
        json={"rating": 5.0, "behavioral_tags": ["Punctual"]},
    )
    assert resp2.json()["status"] == ReviewStatusEnum.COLLUSION_FLAGGED.value
    # Reputation unchanged
    prof2 = (await async_client.get(f"/api/v1/auth/profile/{user_b.id}")).json()
    assert prof2["reputation_score"] == 3.75

    # Case 2: Date 3 completed 32 days after Date 2 (completed 3 hours ago -> outside 30-day cooldown from Date 1)
    # Let's create a pair user_e, user_f whose Date 1 was 32 days ago
    user_e = await test_users_factory(email="fresh_e@example.com", reputation=3.5)
    user_f = await test_users_factory(email="fresh_f@example.com", reputation=3.5)
    headers_e = auth_headers_factory(user_e)
    headers_f = auth_headers_factory(user_f)

    date_past = await _create_completed_date(
        db_session=db_session,
        user_a=user_e,
        user_b=user_f,
        conv_id=2,
        completed_at=now - timedelta(days=32),
    )
    await async_client.post(f"/api/v1/reviews/{date_past.id}", headers=headers_e, json={"rating": 5.0, "behavioral_tags": ["Great"]})
    await async_client.post(f"/api/v1/reviews/{date_past.id}", headers=headers_f, json={"rating": 5.0, "behavioral_tags": ["Great"]})

    # Set the past reviews' creation timestamp to 32 days ago
    from sqlalchemy import update
    await db_session.execute(
        update(DateReview)
        .where(DateReview.date_invitation_id == date_past.id)
        .values(created_at=now - timedelta(days=32))
    )
    await db_session.commit()

    # New date today (32 days later > 30 days cooldown)
    date_eligible = await _create_completed_date(
        db_session=db_session,
        user_a=user_e,
        user_b=user_f,
        conv_id=2,
        completed_at=now - timedelta(hours=3),
    )
    resp_el = await async_client.post(
        f"/api/v1/reviews/{date_eligible.id}",
        headers=headers_e,
        json={"rating": 5.0, "behavioral_tags": ["Great"]},
    )
    # Not flagged for collusion!
    assert resp_el.json()["status"] == ReviewStatusEnum.SUBMITTED_BLIND.value


