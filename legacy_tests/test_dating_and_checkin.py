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


@pytest.mark.asyncio
async def test_date_invitation_time_window_validation(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-009 AC 9.1: Validates scheduled meeting datetime must be between +2 hours and +14 days."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    # 1. Invalid: less than 2 hours in advance (e.g. +30 minutes)
    too_soon = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    resp_soon = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": too_soon,
            "venue_name": "Cafe",
            "venue_address": "Street 1",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    assert resp_soon.status_code == 422

    # 2. Invalid: more than 14 days in advance (e.g. +16 days)
    too_late = (datetime.utcnow() + timedelta(days=16)).isoformat()
    resp_late = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": too_late,
            "venue_name": "Cafe",
            "venue_address": "Street 1",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    assert resp_late.status_code == 422


@pytest.mark.asyncio
async def test_date_invitation_24h_expiration(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-009 AC 9.3: Responding to a date invitation after 24 hours marks it expired and returns ERR_INVALID_DATE_STATE."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    from src.models.dating import DateInvitation
    meeting_time = datetime.utcnow() + timedelta(days=3)
    expired_inv = DateInvitation(
        conversation_id=conv_id,
        initiator_id=user_a.id,
        recipient_id=user_b.id,
        activity_topic="Dinner",
        scheduled_datetime=meeting_time,
        venue_name="Bistro",
        venue_address="West Lake 2",
        venue_latitude=30.25,
        venue_longitude=120.15,
        status=DateStatusEnum.PENDING_ACCEPTANCE,
        created_at=datetime.utcnow() - timedelta(hours=25),  # Created 25 hours ago!
    )
    db_session.add(expired_inv)
    await db_session.commit()
    await db_session.refresh(expired_inv)

    # Recipient attempts to accept after 24h expiration
    resp = await async_client.post(
        f"/api/v1/dates/{expired_inv.id}/respond",
        headers=headers_b,
        json={"action": "accept"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == AppErrorCode.ERR_INVALID_DATE_STATE.value

    # Verify status is now expired in database
    await db_session.refresh(expired_inv)
    assert expired_inv.status == DateStatusEnum.EXPIRED


@pytest.mark.asyncio
async def test_date_respond_and_cancel_authorization(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-009 & US-012: Initiator cannot accept own date, non-participant cannot cancel, and cancelling non-confirmed date fails."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )
    user_c = await test_users_factory(email="outsider_c@example.com")
    headers_c = auth_headers_factory(user_c)

    # Create invitation
    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Tea",
            "scheduled_datetime": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "venue_name": "Tea Garden",
            "venue_address": "Green Road 88",
            "venue_latitude": 30.26,
            "venue_longitude": 120.14,
        },
    )
    date_id = invite_resp.json()["id"]

    # 1. Initiator (User A) tries to accept their own invitation -> 403 ERR_AUTH_REQUIRED
    self_accept_resp = await async_client.post(
        f"/api/v1/dates/{date_id}/respond",
        headers=headers_a,
        json={"action": "accept"},
    )
    assert self_accept_resp.status_code == 403
    assert self_accept_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

    # 2. User A tries to cancel before it is confirmed -> 400 ERR_INVALID_DATE_STATE
    cancel_pending = await async_client.post(
        f"/api/v1/dates/{date_id}/cancel",
        headers=headers_a,
        json={"reason": "Changed my mind"},
    )
    assert cancel_pending.status_code == 400
    assert cancel_pending.json()["error_code"] == AppErrorCode.ERR_INVALID_DATE_STATE.value

    # User B accepts
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # 3. Third-party (User C) tries to cancel the confirmed date -> 403 ERR_AUTH_REQUIRED
    cancel_outsider = await async_client.post(
        f"/api/v1/dates/{date_id}/cancel",
        headers=headers_c,
        json={"reason": "Cancel someone else's date"},
    )
    assert cancel_outsider.status_code == 403
    assert cancel_outsider.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value


@pytest.mark.asyncio
async def test_dynamic_qr_checkin_tamper_and_self_scan_rejection(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010 AC 10.1: Self-scanning, 3rd party scanning, or invalid TOTP QR tokens are rejected."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )
    user_c = await test_users_factory(email="qr_intruder@example.com")
    headers_c = auth_headers_factory(user_c)

    invite_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Dinner",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
            "venue_name": "Seafood Pier",
            "venue_address": "Pier 9",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    date_id = invite_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A generates QR token
    qr_data = (await async_client.post(f"/api/v1/dates/{date_id}/checkin/qr/generate", headers=headers_a)).json()
    qr_token = qr_data["qr_token"]

    # 1. User A tries to scan their own QR code -> 403 ERR_AUTH_REQUIRED
    self_scan = await async_client.post(
        "/api/v1/dates/checkin/qr/scan",
        headers=headers_a,
        json={"qr_token": qr_token},
    )
    assert self_scan.status_code == 403

    # 2. User C (third party) tries to scan User A's QR code -> 403 ERR_AUTH_REQUIRED
    third_party_scan = await async_client.post(
        "/api/v1/dates/checkin/qr/scan",
        headers=headers_c,
        json={"qr_token": qr_token},
    )
    assert third_party_scan.status_code == 403

    # 3. User B scans with a fake / expired TOTP token -> 400 ERR_INVALID_DATE_STATE
    tampered_token = f"DATE_QR:{date_id}:{user_a.id}:000000"
    tampered_scan = await async_client.post(
        "/api/v1/dates/checkin/qr/scan",
        headers=headers_b,
        json={"qr_token": tampered_token},
    )
    assert tampered_scan.status_code == 400


@pytest.mark.asyncio
async def test_gps_anti_spoofing_emulator_detection(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010 AC 10.3 & NFR-SEC-03: x-is-emulator header triggers anti-spoofing defense and returns ERR_GEO_SPOOFING_DETECTED."""
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

    # Header with x-is-emulator: true
    emulator_headers = {**headers_a, "x-is-emulator": "true"}
    resp = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=emulator_headers,
        json={"latitude": venue_lat, "longitude": venue_lon, "is_mock": False},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == AppErrorCode.ERR_GEO_SPOOFING_DETECTED.value


@pytest.mark.asyncio
async def test_date_invitation_scheduled_time_exact_boundaries(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-009 AC 9.1: Scheduled meeting time boundaries (+2h min, +14d max)."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    now = datetime.utcnow()

    # 1. Exactly +2 hours -> Allowed (200)
    time_2h = (now + timedelta(hours=2, minutes=5)).replace(microsecond=0)
    resp_2h = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": time_2h.isoformat(),
            "venue_name": "Corner Cafe",
            "venue_address": "Main Rd 1",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    assert resp_2h.status_code == 200

    # 2. Exactly +14 days -> Allowed (200)
    time_14d = (now + timedelta(days=14)).replace(microsecond=0)
    resp_14d = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Exhibition",
            "scheduled_datetime": time_14d.isoformat(),
            "venue_name": "Art Gallery",
            "venue_address": "Main Rd 2",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    assert resp_14d.status_code == 200


@pytest.mark.asyncio
async def test_cancellation_exact_4h_boundary(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-012 AC 12.1 & 12.2: Cancellation at >= 4h is penalty-free; cancellation at < 4h triggers no-show penalty."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    now = datetime.utcnow()

    # Case 1: Cancelled 4 hours and 10 minutes before meeting (>= 4h)
    meet_time_excused = now + timedelta(hours=4, minutes=10)
    inv1_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Lunch",
            "scheduled_datetime": meet_time_excused.isoformat(),
            "venue_name": "Bistro A",
            "venue_address": "Street A",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    date1_id = inv1_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date1_id}/respond", headers=headers_b, json={"action": "accept"})

    cancel1_resp = await async_client.post(
        f"/api/v1/dates/{date1_id}/cancel",
        headers=headers_a,
        json={"reason": "Excused cancellation in advance"},
    )
    assert cancel1_resp.status_code == 200
    assert cancel1_resp.json()["status"] == "cancelled_excused"

    # Verify no points or reputation penalty for Case 1
    bal1 = await async_client.get("/api/v1/points/balance", headers=headers_a)
    assert bal1.json()["balance"] == 200

    # Case 2: Cancelled 3 hours and 50 minutes before meeting (< 4h)
    meet_time_late = now + timedelta(hours=3, minutes=50)
    inv2_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Dinner",
            "scheduled_datetime": meet_time_late.isoformat(),
            "venue_name": "Bistro B",
            "venue_address": "Street B",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    date2_id = inv2_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date2_id}/respond", headers=headers_b, json={"action": "accept"})

    cancel2_resp = await async_client.post(
        f"/api/v1/dates/{date2_id}/cancel",
        headers=headers_a,
        json={"reason": "Last minute cancel"},
    )
    assert cancel2_resp.status_code == 200
    assert cancel2_resp.json()["status"] == "no_show"

    # Verify -50 points and -0.5 reputation for Case 2: 200 -> 150 points, 4.0 -> 3.5 reputation
    bal2 = await async_client.get("/api/v1/points/balance", headers=headers_a)
    assert bal2.json()["balance"] == 150
    prof2 = await async_client.get(f"/api/v1/auth/profile/{user_a.id}")
    assert prof2.json()["reputation_score"] == 3.5


@pytest.mark.asyncio
async def test_reputation_floor_at_1_0(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-012 AC 12.2: Reputation score is clamped at minimum 1.0 upon penalty deduction."""
    user_a = await test_users_factory(email="low_floor_a@example.com", reputation=1.2, points=100)
    user_b = await test_users_factory(email="low_floor_b@example.com", reputation=4.0, points=100)
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    await async_client.post("/api/v1/recommendations/swipe", headers=headers_a, json={"target_user_id": user_b.id, "action": "like"})
    resp_match = await async_client.post("/api/v1/recommendations/swipe", headers=headers_b, json={"target_user_id": user_a.id, "action": "like"})
    conv_id = resp_match.json()["conversation_id"]

    # Date in 2 hours (<4h)
    inv_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Tea",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "venue_name": "Tea Spot",
            "venue_address": "Street 1",
            "venue_latitude": 30.25,
            "venue_longitude": 120.15,
        },
    )
    date_id = inv_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # User A cancels late (< 4h): reputation 1.2 - 0.5 = 0.7 -> clamped to 1.0!
    await async_client.post(f"/api/v1/dates/{date_id}/cancel", headers=headers_a, json={"reason": "Late cancel"})
    prof = await async_client.get(f"/api/v1/auth/profile/{user_a.id}")
    assert prof.json()["reputation_score"] == 1.0


@pytest.mark.asyncio
async def test_gps_geofence_exact_distance_boundary(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-010 AC 10.2: Validates 100m geofence radius boundary: ~90m succeeds, ~150m fails."""
    user_a, user_b, headers_a, headers_b, conv_id = await _create_matched_pair(
        async_client, test_users_factory, auth_headers_factory
    )

    venue_lat, venue_lon = 30.250000, 120.150000

    inv_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers_a,
        json={
            "conversation_id": conv_id,
            "activity_topic": "Coffee",
            "scheduled_datetime": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
            "venue_name": "Venue",
            "venue_address": "Address",
            "venue_latitude": venue_lat,
            "venue_longitude": venue_lon,
        },
    )
    date_id = inv_resp.json()["id"]
    await async_client.post(f"/api/v1/dates/{date_id}/respond", headers=headers_b, json={"action": "accept"})

    # Check-in at ~90m distance (~0.0008 deg lat delta is ~88 meters) -> succeeds
    resp_within = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_a,
        json={"latitude": 30.25075, "longitude": 120.150000, "is_mock": False},
    )
    assert resp_within.status_code == 200
    assert resp_within.json()["initiator_checked_in"] is True

    # Check-in at ~150m distance (~0.0014 deg lat delta is ~155 meters) -> fails
    resp_outside = await async_client.post(
        f"/api/v1/dates/{date_id}/checkin/gps",
        headers=headers_b,
        json={"latitude": 30.25140, "longitude": 120.150000, "is_mock": False},
    )
    assert resp_outside.status_code == 400
    assert resp_outside.json()["error_code"] == AppErrorCode.ERR_INVALID_DATE_STATE.value


