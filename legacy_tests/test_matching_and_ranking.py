"""Validates US-005, US-006, US-007, US-014, US-015: 10-card quota, exposure score, mutual match, targeted search, and refresh."""

from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient

from src.models.user import (
    GenderEnum,
    DatingPreferenceEnum,
    VerificationStatusEnum,
    SchoolTierEnum,
    DegreeLevelEnum,
)
from src.core.exceptions import AppErrorCode
from src.services.matching_service import MatchingService


@pytest.mark.asyncio
async def test_multi_factor_exposure_ranking_formula(test_users_factory):
    """US-006: Score = 0.70 * BayesianReputationScore + 0.20 * ColdStartBonus + 0.10 * RecencyBonus."""
    now = datetime.utcnow()

    # User 1: High reputation (4.8), verified 24h ago (cold start = 1.0), active 1h ago (recency = 1.0)
    # Score = 0.70 * 4.8 + 0.20 * 1.0 + 0.10 * 1.0 = 3.36 + 0.20 + 0.10 = 3.66
    u1 = await test_users_factory(
        email="candidate1@example.com",
        reputation=4.8,
        verified_at=now - timedelta(hours=24),
    )
    score1 = MatchingService.calculate_exposure_score(u1, current_time=now)
    assert score1 == 3.66

    # User 2: Baseline reputation (3.5), verified 100h ago (cold start = 0.0), active 72h ago (recency = 0.0)
    # Score = 0.70 * 3.5 + 0.20 * 0.0 + 0.10 * 0.0 = 2.45
    u2 = await test_users_factory(
        email="candidate2@example.com",
        reputation=3.5,
        verified_at=now - timedelta(hours=100),
    )
    u2.last_active_at = now - timedelta(hours=72)
    score2 = MatchingService.calculate_exposure_score(u2, current_time=now)
    assert score2 == 2.45


@pytest.mark.asyncio
async def test_daily_10_card_quota_and_exhaustion(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-005: Daily 10-candidate card quota and single-day swipe/skip card decrement."""
    main_user = await test_users_factory(
        email="swiper@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers = auth_headers_factory(main_user)

    # Create 12 female candidate profiles
    candidates = []
    for i in range(12):
        c = await test_users_factory(
            email=f"female_cand_{i}@example.com",
            nickname=f"Cand_{i}",
            gender=GenderEnum.FEMALE,
            preference=DatingPreferenceEnum.MALE,
            reputation=3.5 + (i * 0.1),
        )
        candidates.append(c)

    # Initial deck fetch -> returns 10 candidates (the quota)
    resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["remaining_cards"] == 10
    assert len(data["candidates"]) == 10

    # Swipe 1 card
    target_id = data["candidates"][0]["id"]
    swipe_resp = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers,
        json={"target_user_id": target_id, "action": "skip"},
    )
    assert swipe_resp.status_code == 200
    swipe_data = swipe_resp.json()
    assert swipe_data["remaining_cards"] == 9
    assert swipe_data["is_match"] is False

    # Check deck remaining count is now 9
    deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert deck_resp.json()["remaining_cards"] == 9


@pytest.mark.asyncio
async def test_double_opt_in_matching_and_im_creation(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-007: Single-side like remains anonymous; reciprocal like establishes mutual match & initializes 1v1 IM."""
    user_a = await test_users_factory(
        email="romeo@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    user_b = await test_users_factory(
        email="juliet@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
    )
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    # User A likes User B
    resp_a = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_a,
        json={"target_user_id": user_b.id, "action": "like"},
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["is_match"] is False  # Anonymous single-side like!

    # User B likes User A back -> Mutual Match!
    resp_b = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_b,
        json={"target_user_id": user_a.id, "action": "like"},
    )
    assert resp_b.status_code == 200
    match_data = resp_b.json()
    assert match_data["is_match"] is True
    assert match_data["match_id"] is not None
    assert match_data["conversation_id"] is not None


@pytest.mark.asyncio
async def test_targeted_discovery_and_crush_application(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-014: Consumes 100 points for top 10% search and sends direct crush application with 200-char note."""
    seeker = await test_users_factory(
        email="seeker@example.com",
        points=150,
        city="Hangzhou",
    )
    headers = auth_headers_factory(seeker)

    # Create top candidate
    star = await test_users_factory(
        email="star@example.com",
        nickname="StarProfile",
        reputation=4.9,
        city="Hangzhou",
    )

    # Targeted search
    search_resp = await async_client.post(
        "/api/v1/recommendations/targeted-search",
        headers=headers,
        json={"city": "Hangzhou", "top_percentile": 0.50},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert any(c["id"] == star.id for c in results)

    # Check points were deducted: 150 - 100 = 50
    bal_resp = await async_client.get("/api/v1/points/balance", headers=headers)
    assert bal_resp.json()["balance"] == 50

    # Send Crush Application
    crush_resp = await async_client.post(
        "/api/v1/recommendations/crush-application",
        headers=headers,
        json={
            "target_user_id": star.id,
            "intro_note": "Hi, I admire your passion for literature and would love to connect!",
        },
    )
    assert crush_resp.status_code == 200
    assert crush_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_paid_recommendation_pack_refresh_limit(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-015: 30 points buys 5 extra cards, max 1 refresh per day."""
    user = await test_users_factory(
        email="refresher@example.com",
        points=100,
    )
    headers = auth_headers_factory(user)

    # First refresh: succeeds
    r1 = await async_client.post("/api/v1/recommendations/refresh-pack", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["cards_added"] == 5
    assert r1.json()["remaining_balance"] == 70

    # Second refresh on same day: fails with ERR_DAILY_REFRESH_LIMIT_REACHED
    r2 = await async_client.post("/api/v1/recommendations/refresh-pack", headers=headers)
    assert r2.status_code == 400
    assert r2.json()["error_code"] == AppErrorCode.ERR_DAILY_REFRESH_LIMIT_REACHED.value


@pytest.mark.asyncio
async def test_daily_deck_full_exhaustion_to_empty_and_reset_countdown(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-005 AC 5.3: Completing all 10 swipes returns empty deck response with countdown to midnight reset."""
    swiper = await test_users_factory(
        email="exhaust_swiper@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers = auth_headers_factory(swiper)

    # Create 10 candidates
    for i in range(10):
        await test_users_factory(
            email=f"cand_exhaust_{i}@example.com",
            nickname=f"CandExhaust_{i}",
            gender=GenderEnum.FEMALE,
            preference=DatingPreferenceEnum.MALE,
        )

    # Initial deck fetch -> 10 candidates
    d_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert d_resp.status_code == 200
    deck_data = d_resp.json()
    assert deck_data["remaining_cards"] == 10
    cand_ids = [c["id"] for c in deck_data["candidates"]]

    # Swipe all 10 cards
    for idx, cid in enumerate(cand_ids):
        action = "like" if idx % 2 == 0 else "skip"
        sw_res = await async_client.post(
            "/api/v1/recommendations/swipe",
            headers=headers,
            json={"target_user_id": cid, "action": action},
        )
        assert sw_res.status_code == 200
        assert sw_res.json()["remaining_cards"] == 9 - idx

    # Deck is now completely exhausted!
    exhausted_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert exhausted_resp.status_code == 200
    ex_data = exhausted_resp.json()
    assert ex_data["remaining_cards"] == 0
    assert len(ex_data["candidates"]) == 0
    assert ex_data["seconds_until_reset"] > 0


@pytest.mark.asyncio
async def test_daily_deck_exposure_score_ranking_order(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-006 AC 6.4: Candidates in daily deck appear ordered strictly by multi-factor exposure ranking score."""
    user = await test_users_factory(
        email="ranking_checker@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers = auth_headers_factory(user)

    now = datetime.utcnow()
    # Create candidates with distinct reputations & activity levels
    c1 = await test_users_factory(
        email="rank_low@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        reputation=3.2,
        verified_at=now - timedelta(hours=100),  # no cold start
    )
    c1.last_active_at = now - timedelta(hours=80)  # no recency

    c2 = await test_users_factory(
        email="rank_high@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        reputation=4.9,
        verified_at=now - timedelta(hours=20),  # cold start 1.0
    )
    c2.last_active_at = now - timedelta(hours=2)  # recency 1.0

    c3 = await test_users_factory(
        email="rank_mid@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        reputation=4.0,
        verified_at=now - timedelta(hours=100),  # no cold start
    )
    c3.last_active_at = now - timedelta(hours=5)  # recency 1.0

    deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert deck_resp.status_code == 200
    candidates = deck_resp.json()["candidates"]

    # Verify descending ordering of ranking scores
    scores = [c["ranking_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_exposure_score_cold_start_and_recency_boundaries(test_users_factory):
    """US-006 AC 6.2 & 6.3: Cold start bonus drops to 0.0 after 72h; recency bonus drops to 0.0 after 48h."""
    now = datetime.utcnow()

    # 1. Cold start boundary: 71 hours (within 72h -> 1.0 bonus)
    u_cs_active = await test_users_factory(
        email="cs71@example.com",
        reputation=3.5,
        verified_at=now - timedelta(hours=71),
    )
    u_cs_active.last_active_at = now - timedelta(hours=50)  # inactive > 48h
    # Score = 0.70*3.5 + 0.20*1.0 + 0.10*0.0 = 2.45 + 0.20 = 2.65
    assert MatchingService.calculate_exposure_score(u_cs_active, current_time=now) == 2.65

    # 2. Cold start boundary: 73 hours (past 72h -> 0.0 bonus)
    u_cs_expired = await test_users_factory(
        email="cs73@example.com",
        reputation=3.5,
        verified_at=now - timedelta(hours=73),
    )
    u_cs_expired.last_active_at = now - timedelta(hours=50)
    # Score = 0.70*3.5 + 0.20*0.0 + 0.10*0.0 = 2.45
    assert MatchingService.calculate_exposure_score(u_cs_expired, current_time=now) == 2.45

    # 3. Recency boundary: 47 hours (within 48h -> 1.0 bonus)
    u_rec_active = await test_users_factory(
        email="rec47@example.com",
        reputation=3.5,
        verified_at=now - timedelta(hours=100),  # past 72h
    )
    u_rec_active.last_active_at = now - timedelta(hours=47)
    # Score = 0.70*3.5 + 0.20*0.0 + 0.10*1.0 = 2.45 + 0.10 = 2.55
    assert MatchingService.calculate_exposure_score(u_rec_active, current_time=now) == 2.55

    # 4. Recency boundary: 49 hours (past 48h -> 0.0 bonus)
    u_rec_expired = await test_users_factory(
        email="rec49@example.com",
        reputation=3.5,
        verified_at=now - timedelta(hours=100),
    )
    u_rec_expired.last_active_at = now - timedelta(hours=49)
    # Score = 0.70*3.5 + 0.20*0.0 + 0.10*0.0 = 2.45
    assert MatchingService.calculate_exposure_score(u_rec_expired, current_time=now) == 2.45


@pytest.mark.asyncio
async def test_crush_application_to_nonexistent_candidate(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-014: Sending crush application to invalid/non-existent user returns 404 ERR_NOT_FOUND."""
    user = await test_users_factory(email="crush_sender@example.com", points=100)
    headers = auth_headers_factory(user)

    resp = await async_client.post(
        "/api/v1/recommendations/crush-application",
        headers=headers,
        json={"target_user_id": 999999, "intro_note": "Hello there!"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == AppErrorCode.ERR_NOT_FOUND.value


@pytest.mark.asyncio
async def test_gender_and_dating_preference_filtering(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-001 & US-005: Recommendation pool strictly filters candidate profiles based on mutual dating preferences."""
    # User A: Male seeking Female
    user_a = await test_users_factory(
        email="male_seeker@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers_a = auth_headers_factory(user_a)

    # Candidate 1: Female seeking Male (Compatible)
    c1 = await test_users_factory(
        email="c_fem_seek_male@example.com",
        nickname="CompatibleFem1",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
    )
    # Candidate 2: Female seeking Both (Compatible)
    c2 = await test_users_factory(
        email="c_fem_seek_both@example.com",
        nickname="CompatibleFem2",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.BOTH,
    )
    # Candidate 3: Female seeking Female (Incompatible for User A)
    c3 = await test_users_factory(
        email="c_fem_seek_fem@example.com",
        nickname="IncompatibleFem3",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    # Candidate 4: Male seeking Female (Incompatible gender for User A)
    c4 = await test_users_factory(
        email="c_male_seek_fem@example.com",
        nickname="IncompatibleMale4",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )

    deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers_a)
    assert deck_resp.status_code == 200
    candidates = deck_resp.json()["candidates"]
    candidate_ids = [c["id"] for c in candidates]

    assert c1.id in candidate_ids
    assert c2.id in candidate_ids
    assert c3.id not in candidate_ids
    assert c4.id not in candidate_ids


@pytest.mark.asyncio
async def test_low_reputation_deprioritization_in_deck(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-006 & US-012 AC 12.3: Candidates with low reputation score (< 3.0) receive lower ranking scores and rank below standard candidates."""
    user = await test_users_factory(
        email="deck_inspector@example.com",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers = auth_headers_factory(user)

    now = datetime.utcnow()
    # Candidate with penalized low reputation 2.0 (e.g. from no-shows)
    low_rep = await test_users_factory(
        email="low_rep_user@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        reputation=2.0,
        verified_at=now - timedelta(hours=100),
    )
    low_rep.last_active_at = now - timedelta(hours=80)

    # Candidate with standard baseline reputation 3.5
    standard_rep = await test_users_factory(
        email="std_rep_user@example.com",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        reputation=3.5,
        verified_at=now - timedelta(hours=100),
    )
    standard_rep.last_active_at = now - timedelta(hours=80)

    score_low = MatchingService.calculate_exposure_score(low_rep, current_time=now)
    score_std = MatchingService.calculate_exposure_score(standard_rep, current_time=now)
    # 0.70 * 2.0 = 1.40 vs 0.70 * 3.5 = 2.45
    assert score_low == 1.40
    assert score_std == 2.45
    assert score_low < score_std

    deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert deck_resp.status_code == 200
    cands = deck_resp.json()["candidates"]
    cand_ids = [c["id"] for c in cands]
    # Standard candidate ranks ahead of low reputation candidate
    assert cand_ids.index(standard_rep.id) < cand_ids.index(low_rep.id)


@pytest.mark.asyncio
async def test_crush_application_intro_note_length_validation(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-014 AC 14.2: Crush application introductory note allows up to 200 characters; rejects > 200 or empty."""
    sender = await test_users_factory(email="crush_author@example.com", points=100)
    target = await test_users_factory(email="crush_beloved@example.com")
    headers = auth_headers_factory(sender)

    # Exactly 200 characters -> Succeeds (200)
    note_200 = "A" * 200
    resp_200 = await async_client.post(
        "/api/v1/recommendations/crush-application",
        headers=headers,
        json={"target_user_id": target.id, "intro_note": note_200},
    )
    assert resp_200.status_code == 200
    assert resp_200.json()["success"] is True

    # 201 characters -> Rejected (422)
    note_201 = "A" * 201
    resp_201 = await async_client.post(
        "/api/v1/recommendations/crush-application",
        headers=headers,
        json={"target_user_id": target.id, "intro_note": note_201},
    )
    assert resp_201.status_code == 422

    # Empty note (0 characters) -> Rejected (422)
    resp_empty = await async_client.post(
        "/api/v1/recommendations/crush-application",
        headers=headers,
        json={"target_user_id": target.id, "intro_note": ""},
    )
    assert resp_empty.status_code == 422


@pytest.mark.asyncio
async def test_targeted_search_insufficient_points_exact_boundary(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-014 AC 14.3: Targeted search requires 100 points; 99 points is rejected with 402; exactly 100 succeeds."""
    # 99 points: fails
    u99 = await test_users_factory(email="pts99@example.com", points=99, city="Shanghai")
    h99 = auth_headers_factory(u99)
    r99 = await async_client.post(
        "/api/v1/recommendations/targeted-search",
        headers=h99,
        json={"city": "Shanghai", "top_percentile": 0.10},
    )
    assert r99.status_code == 402
    assert r99.json()["error_code"] == AppErrorCode.ERR_INSUFFICIENT_POINTS.value

    # Exactly 100 points: succeeds and balance becomes 0
    u100 = await test_users_factory(email="pts100@example.com", points=100, city="Shanghai")
    h100 = auth_headers_factory(u100)
    r100 = await async_client.post(
        "/api/v1/recommendations/targeted-search",
        headers=h100,
        json={"city": "Shanghai", "top_percentile": 0.10},
    )
    assert r100.status_code == 200
    bal_r = await async_client.get("/api/v1/points/balance", headers=h100)
    assert bal_r.json()["balance"] == 0


@pytest.mark.asyncio
async def test_pack_refresh_insufficient_points_exact_boundary(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-015 AC 15.3: Pack refresh requires 30 points; 29 points is rejected with 402; exactly 30 succeeds."""
    # 29 points: fails
    u29 = await test_users_factory(email="pts29@example.com", points=29)
    h29 = auth_headers_factory(u29)
    r29 = await async_client.post("/api/v1/recommendations/refresh-pack", headers=h29)
    assert r29.status_code == 402
    assert r29.json()["error_code"] == AppErrorCode.ERR_INSUFFICIENT_POINTS.value

    # Exactly 30 points: succeeds and balance becomes 0
    u30 = await test_users_factory(email="pts30@example.com", points=30)
    h30 = auth_headers_factory(u30)
    r30 = await async_client.post("/api/v1/recommendations/refresh-pack", headers=h30)
    assert r30.status_code == 200
    assert r30.json()["remaining_balance"] == 0


@pytest.mark.asyncio
async def test_swipe_skip_does_not_trigger_match(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-007 AC 7.1: If User A likes User B, but User B skips User A, no match or conversation is created."""
    user_a = await test_users_factory(email="liker_a@example.com")
    user_b = await test_users_factory(email="skipper_b@example.com")
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    # User A likes User B
    resp_a = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_a,
        json={"target_user_id": user_b.id, "action": "like"},
    )
    assert resp_a.json()["is_match"] is False

    # User B skips User A
    resp_b = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_b,
        json={"target_user_id": user_a.id, "action": "skip"},
    )
    assert resp_b.json()["is_match"] is False
    assert resp_b.json()["conversation_id"] is None


