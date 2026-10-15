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
