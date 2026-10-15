"""Validates US-013, US-014, US-015: milestone awards, idempotency deduplication, insufficient points rejection, and ledger consistency."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.points import PointReasonEnum, PointLedger
from src.core.exceptions import AppErrorCode, InsufficientPointsException
from src.services.points_service import PointsService


@pytest.mark.asyncio
async def test_points_milestone_accrual(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-013: Milestone awards (+100 edu, +5 login, +30 date >= 4.5, +50 report) are credited immediately with immutable ledger entries."""
    user = await test_users_factory(email="milestone@example.com", points=0)
    headers = auth_headers_factory(user)

    # 1. Milestone: Education verification award (+100)
    await PointsService.award_points(
        db=db_session,
        user=user,
        amount=100,
        reason=PointReasonEnum.EDUCATION_VERIFIED,
        idempotency_key=f"edu_verified_{user.id}",
        description="Education degree verified (+100 bonus)",
    )

    # 2. Milestone: Daily login check-in (+5)
    checkin_resp = await async_client.post("/api/v1/points/checkin", headers=headers)
    assert checkin_resp.status_code == 200
    assert checkin_resp.json()["success"] is True
    assert checkin_resp.json()["points_awarded"] == 5

    # 3. Milestone: High-rating date review (+30)
    await PointsService.award_points(
        db=db_session,
        user=user,
        amount=30,
        reason=PointReasonEnum.HIGH_RATING_DATE,
        idempotency_key=f"high_rating_date_1_{user.id}",
        description="Received 5-star date rating (+30 reward)",
    )

    # 4. Milestone: Confirmed report (+50)
    await PointsService.award_points(
        db=db_session,
        user=user,
        amount=50,
        reason=PointReasonEnum.CONFIRMED_REPORT,
        idempotency_key=f"report_verified_1_{user.id}",
        description="Report verified against violator (+50 reward)",
    )

    # Total balance: 0 + 100 + 5 + 30 + 50 = 185
    bal_resp = await async_client.get("/api/v1/points/balance", headers=headers)
    assert bal_resp.status_code == 200
    data = bal_resp.json()
    assert data["balance"] == 185
    assert len(data["transactions"]) == 4


@pytest.mark.asyncio
async def test_points_award_idempotency(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-013: Submitting point awards with identical idempotency key processes only the initial award without double-crediting."""
    user = await test_users_factory(email="idempotent@example.com", points=50)
    headers = auth_headers_factory(user)

    idempotency_key = "unique_bonus_event_123"

    # First attempt: credits +100
    e1 = await PointsService.award_points(
        db=db_session,
        user=user,
        amount=100,
        reason=PointReasonEnum.EDUCATION_VERIFIED,
        idempotency_key=idempotency_key,
        description="Initial bonus",
    )
    assert user.points_balance == 150

    # Second attempt with same key: ignored, returns existing ledger record
    e2 = await PointsService.award_points(
        db=db_session,
        user=user,
        amount=100,
        reason=PointReasonEnum.EDUCATION_VERIFIED,
        idempotency_key=idempotency_key,
        description="Duplicate bonus attempt",
    )
    assert e1.id == e2.id
    assert user.points_balance == 150  # NOT 250!

    # Test daily check-in endpoint idempotency on the same day
    c1 = await async_client.post("/api/v1/points/checkin", headers=headers)
    assert c1.json()["success"] is True
    assert c1.json()["points_awarded"] == 5
    assert c1.json()["current_balance"] == 155

    # Second check-in today: no additional points
    c2 = await async_client.post("/api/v1/points/checkin", headers=headers)
    assert c2.json()["success"] is False
    assert c2.json()["points_awarded"] == 0
    assert c2.json()["current_balance"] == 155


@pytest.mark.asyncio
async def test_insufficient_points_rejection(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-014 & US-015: Attempts to spend points without sufficient balance abort with HTTP 402 ERR_INSUFFICIENT_POINTS."""
    poor_user = await test_users_factory(email="poor@example.com", points=15, city="Hangzhou")
    headers = poor_user_headers = auth_headers_factory(poor_user)

    # 1. Targeted search requires 100 points, user only has 15
    search_resp = await async_client.post(
        "/api/v1/recommendations/targeted-search",
        headers=headers,
        json={"city": "Hangzhou", "top_percentile": 0.10},
    )
    assert search_resp.status_code == 402
    assert search_resp.json()["error_code"] == AppErrorCode.ERR_INSUFFICIENT_POINTS.value

    # 2. Recommendation pack refresh requires 30 points, user only has 15
    refresh_resp = await async_client.post(
        "/api/v1/recommendations/refresh-pack",
        headers=headers,
    )
    assert refresh_resp.status_code == 402
    assert refresh_resp.json()["error_code"] == AppErrorCode.ERR_INSUFFICIENT_POINTS.value


@pytest.mark.asyncio
async def test_point_ledger_audit_trail(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-013: Point ledger maintains an immutable audit trail with running balances, paginated queries, and reason codes."""
    user = await test_users_factory(email="audittrail@example.com", points=0)
    headers = auth_headers_factory(user)

    # Perform sequence of transactions
    # 1. +100
    await PointsService.award_points(
        db=db_session,
        user=user,
        amount=100,
        reason=PointReasonEnum.EDUCATION_VERIFIED,
        idempotency_key="tx_1",
        description="Education verification",
    )
    # 2. -30
    await PointsService.deduct_points(
        db=db_session,
        user=user,
        amount=30,
        reason=PointReasonEnum.EXTRA_PACK_REFRESH,
        idempotency_key="tx_2",
        description="Pack refresh",
    )
    # 3. +50
    await PointsService.award_points(
        db=db_session,
        user=user,
        amount=50,
        reason=PointReasonEnum.CONFIRMED_REPORT,
        idempotency_key="tx_3",
        description="Report reward",
    )

    # Query ledger via API
    resp = await async_client.get("/api/v1/points/balance?limit=2&offset=0", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == 120  # 100 - 30 + 50 = 120
    assert len(data["transactions"]) == 2  # paginated limit 2

    # Verify latest transaction: tx_3 (+50, balance_after=120)
    latest = data["transactions"][0]
    assert latest["amount"] == 50
    assert latest["balance_after"] == 120
    assert latest["reason"] == "CONFIRMED_REPORT"

    # Query offset 2
    resp_page2 = await async_client.get("/api/v1/points/balance?limit=2&offset=2", headers=headers)
    data_page2 = resp_page2.json()
    assert len(data_page2["transactions"]) == 1
    oldest = data_page2["transactions"][0]
    assert oldest["amount"] == 100
    assert oldest["balance_after"] == 100
    assert oldest["reason"] == "EDUCATION_VERIFIED"
