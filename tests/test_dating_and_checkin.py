"""Validates US-009, US-010, US-012: in-chat structured invitations, 24h expiration, dynamic TOTP QR scanning, 100m GPS geofencing, anti-spoofing defense, and 4h cancellation vs no-show penalties."""

from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import GenderEnum, DatingPreferenceEnum
from src.models.dating import DateStatusEnum
from src.core.exceptions import AppErrorCode
from src.services.dating_service import DatingService


async def _create_matched_pair(async_client: AsyncClient, test_users_factory, auth_headers_factory):
    """Helper to create matched user A and user B with an open conversation."""
    user_a = await test_users_factory(
        email="date_a@example.com",
        nickname="DateHost",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
        points=200,
        reputation=4.0,
    )
    user_b = await test_users_factory(
        email="date_b@example.com",
        nickname="DateGuest",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
        points=200,
        reputation=4.0,
    )
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    # Establish mutual match
    await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_a,
        json={"target_user_id": user_b.id, "action": "like"},
    )
    resp = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_b,
        json={"target_user_id": user_a.id, "action": "like"},
    )
    conv_id = resp.json()["conversation_id"]
    return user_a, user_b, headers_a, headers_b, conv_id


@pytest.mark.asyncio
async def test_date_invitation_lifecycle(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-009: Proposes structured date invitation inside chat, recipient accepts within 24h -> confirmed_pending_arrival."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    meeting_time = (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0)

    # User A initiates a date invitation
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": meeting_time.isoformat(),
            "venue_name": "Arabica Coffee",
            "venue_address": "West Lake Cultural Plaza, Hangzhou",
            "venue_latitude": 30.2741,
            "venue_longitude": 120.1551,
        },
    )
    assert invite_resp.status_code == 200
    invite_data = invite_resp.json()
    date_id = invite_data["id"]
    assert invite_data["status"] == "pending_acceptance"
    assert invite_data["activity_topic"] == "Coffee"
    assert invite_data["venue_name"] == "Arabica Coffee"

    # Verify Date Invitation card is rendered in conversation messages
    msgs_resp = await async_client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=headers_a)
    messages = msgs_resp.json()
    assert any(m["message_type"] == "date_invite" for m in messages)

    # User B accepts the invitation
    respond_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/respond",
        headers=headers_b,
        json={"action": "accept"},
    )
    assert respond_resp.status_code == 200
    assert respond_resp.json()["status"] == "confirmed_pending_arrival"

    # Test decline on another invite
    invite2_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Art Exhibition",
            "scheduled_datetime": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            "venue_name": "Zhejiang Art Museum",
            "venue_address": "Nanshan Road 138, Hangzhou",
            "venue_latitude": 30.2330,
            "venue_longitude": 120.1500,
        },
    )
    date2_id = invite2_resp.json()["id"]
    decline_resp = await async_client.post(
        f"/api/v1/dates/{date2_id}/respond",
        headers=headers_b,
        json={"action": "decline"},
    )
    assert decline_resp.status_code == 200
    assert decline_resp.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_dual_dynamic_qr_checkin(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010: Dynamic TOTP QR generation (60s) and mutual scanning certifies arrival and marks date completed."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    # Create and accept date
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Dining",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
            "venue_name": "Grand Bistro",
            "venue_address": "Hubin Pedestrian Street, Hangzhou",
            "venue_latitude": 30.2550,
            "venue_longitude": 120.1600,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A generates dynamic QR token
    qr_gen_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/qr/generate",
        headers=headers_a,
    )
    assert qr_gen_resp.status_code == 200
    qr_data = qr_gen_resp.json()
    assert qr_data["valid_seconds"] == 60
    assert qr_data["date_id"] == date_id
    qr_token = qr_data["qr_token"]

    # User B scans the dynamic QR code
    scan_resp = await async_client.post(
        "/api/v1/dates/checkin/qr/scan",
        headers=headers_b,
        json={"qr_token": qr_token},
    )
    assert scan_resp.status_code == 200
    completed_date = scan_resp.json()
    assert completed_date["status"] == "completed"
    assert completed_date["initiator_checked_in"] is True
    assert completed_date["recipient_checked_in"] is True


@pytest.mark.asyncio
async def test_gps_geofence_checkin_success(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010: Both participants check in within 100 meters of the designated POI venue, completing the date."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    venue_lat, venue_lon = 30.255000, 120.160000

    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Tea House",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
            "venue_name": "Lakeside Teahouse",
            "venue_address": "Hubin Road 28",
            "venue_latitude": venue_lat,
            "venue_longitude": venue_lon,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A checks in ~30 meters away from venue
    user_a_lat, user_a_lon = 30.255200, 120.160100
    gps_a_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_a,
        json={"latitude": user_a_lat, "longitude": user_a_lon, "is_mock": False},
    )
    assert gps_a_resp.status_code == 200
    assert gps_a_resp.json()["initiator_checked_in"] is True
    assert gps_a_resp.json()["status"] == "confirmed_pending_arrival"  # Waiting for user B

    # User B checks in ~50 meters away
    user_b_lat, user_b_lon = 30.255300, 120.160200
    gps_b_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_b,
        json={"latitude": user_b_lat, "longitude": user_b_lon, "is_mock": False},
    )
    assert gps_b_resp.status_code == 200
    assert gps_b_resp.json()["recipient_checked_in"] is True
    assert gps_b_resp.json()["status"] == "completed"  # Both checked in -> completed!


@pytest.mark.asyncio
async def test_gps_spoofing_detection_rejection(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010: Rejects simulated GPS / mock location / emulator hooks with ERR_GEO_SPOOFING_DETECTED."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    venue_lat, venue_lon = 30.255000, 120.160000
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
            "venue_name": "Lakeside Cafe",
            "venue_address": "Hubin Road 10",
            "venue_latitude": venue_lat,
            "venue_longitude": venue_lon,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # 1. Payload with is_mock=True
    mock_payload_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_a,
        json={"latitude": venue_lat, "longitude": venue_lon, "is_mock": True},
    )
    assert mock_payload_resp.status_code == 403
    assert mock_payload_resp.json()["error_code"] == AppErrorCode.ERR_GEO_SPOOFING_DETECTED.value

    # 2. Header with x-mock-location: true
    spoofed_headers = {**headers_a, "x-mock-location": "true"}
    mock_header_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=spoofed_headers,
        json={"latitude": venue_lat, "longitude": venue_lon, "is_mock": False},
    )
    assert mock_header_resp.status_code == 403
    assert mock_header_resp.json()["error_code"] == AppErrorCode.ERR_GEO_SPOOFING_DETECTED.value

    # 3. Header with x-hook-detected: true
    hook_headers = {**headers_a, "x-hook-detected": "true"}
    hook_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=hook_headers,
        json={"latitude": venue_lat, "longitude": venue_lon, "is_mock": False},
    )
    assert hook_resp.status_code == 403
    assert hook_resp.json()["error_code"] == AppErrorCode.ERR_GEO_SPOOFING_DETECTED.value

    # 4. Out of geofence (> 100 meters, e.g. 5 km away)
    far_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_a,
        json={"latitude": 30.300000, "longitude": 120.200000, "is_mock": False},
    )
    assert far_resp.status_code == 400
    assert far_resp.json()["error_code"] == AppErrorCode.ERR_INVALID_DATE_STATE.value


@pytest.mark.asyncio
async def test_date_cancellation_excused_window(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-012: Cancellation >= 4h prior results in cancelled_excused with 0 reputation or point deduction."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    # Date scheduled 24 hours from now (well above the 4h threshold)
    meeting_time = datetime.utcnow() + timedelta(hours=24)
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Dinner",
            "scheduled_datetime": meeting_time.isoformat(),
            "venue_name": "Italian Kitchen",
            "venue_address": "Jiaogong Road 50",
            "venue_latitude": 30.28,
            "venue_longitude": 120.13,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A cancels >= 4 hours before
    cancel_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/cancel",
        headers=headers_a,
        json={"reason": "Sudden overtime work schedule"},
    )
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "cancelled_excused"

    # Verify no points or reputation penalty
    bal_resp = await async_client.get("/api/v1/points/balance", headers=headers_a)
    assert bal_resp.json()["balance"] == 200

    profile_resp = await async_client.get(f"/api/v1/auth/profile/{user_a.id}")
    assert profile_resp.json()["reputation_score"] == 4.0


@pytest.mark.asyncio
async def test_no_show_penalty_deductions(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-012: Late cancellation (< 4h) or scheduled no-show deducts 0.5 reputation and 50 points."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    # Date scheduled 2 hours from now (< 4 hours threshold)
    meeting_time = datetime.utcnow() + timedelta(hours=2)
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Movie",
            "scheduled_datetime": meeting_time.isoformat(),
            "venue_name": "Cinema City",
            "venue_address": "Yanan Road 100",
            "venue_latitude": 30.26,
            "venue_longitude": 120.16,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A cancels late (< 4h)
    late_cancel_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/cancel",
        headers=headers_a,
        json={"reason": "Cannot make it"},
    )
    assert late_cancel_resp.status_code == 200
    assert late_cancel_resp.json()["status"] == "no_show"

    # Verify -50 points deducted: 200 - 50 = 150
    bal_resp = await async_client.get("/api/v1/points/balance", headers=headers_a)
    assert bal_resp.json()["balance"] == 150

    # Verify -0.5 reputation score deducted: 4.0 -> 3.5
    profile_resp = await async_client.get(f"/api/v1/auth/profile/{user_a.id}")
    assert profile_resp.json()["reputation_score"] == 3.5

    # Also test scheduled background no-show penalty task
    user_c = await test_users_factory(email="noshow_c@example.com", reputation=4.0, points=100)
    user_d = await test_users_factory(email="noshow_d@example.com", reputation=4.0, points=100)
    headers_c = auth_headers_factory(user_c)
    headers_d = auth_headers_factory(user_d)

    await async_client.post("/api/v1/recommendations/swipe", headers=headers_c, json={"target_user_id": user_d.id, "action": "like"})
    resp_cd = await async_client.post("/api/v1/recommendations/swipe", headers=headers_d, json={"target_user_id": user_c.id, "action": "like"})
    conv_cd = resp_cd.json()["conversation_id"]

    # Date was scheduled 2 hours ago and neither user arrived
    from src.models.dating import DateInvitation
    past_date = DateInvitation(
        conversation_id=conv_cd,
        initiator_id=user_c.id,
        recipient_id=user_d.id,
        activity_topic="Lunch",
        scheduled_datetime=datetime.utcnow() - timedelta(hours=2),
        venue_name="Noodle House",
        venue_address="Center Street 5",
        venue_latitude=30.25,
        venue_longitude=120.15,
        status=DateStatusEnum.CONFIRMED_PENDING_ARRIVAL,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(past_date)
    await db_session.commit()

    # Trigger process_no_show_penalties with 60 min cutoff
    penalized = await DatingService.process_no_show_penalties(db_session, grace_period_minutes=60)
    assert penalized >= 1

    # Check that user C was penalized
    bal_c = await async_client.get("/api/v1/points/balance", headers=headers_c)
    assert bal_c.json()["balance"] == 50
