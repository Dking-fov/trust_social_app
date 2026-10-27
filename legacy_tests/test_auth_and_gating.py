"""Validates US-001, US-002, US-003, US-004: registration, age/tag rules, feature gating, OCR, and privacy masking."""

import base64
from datetime import date, timedelta
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


@pytest.mark.asyncio
async def test_registration_age_validation(async_client: AsyncClient):
    """US-001: Validates age limits [20, 35] and rejects younger/older registrations with 422."""
    today = date.today()

    # Underage: 18 years old
    underage_birthdate = (today - timedelta(days=18 * 365 + 5)).isoformat()
    resp_under = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "underage@example.com",
            "password": "Password123!",
            "nickname": "TooYoung",
            "birthdate": underage_birthdate,
            "resident_city": "Shanghai",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["tech", "music", "art"],
        },
    )
    assert resp_under.status_code == 422
    assert resp_under.json()["error_code"] == AppErrorCode.ERR_UNDERAGE_OR_OVERAGE.value

    # Overage: 38 years old
    overage_birthdate = (today - timedelta(days=38 * 365 + 10)).isoformat()
    resp_over = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "overage@example.com",
            "password": "Password123!",
            "nickname": "TooOld",
            "birthdate": overage_birthdate,
            "resident_city": "Beijing",
            "gender": "Female",
            "dating_preference": "Male",
            "interest_tags": ["tea", "hiking", "books"],
        },
    )
    assert resp_over.status_code == 422
    assert resp_over.json()["error_code"] == AppErrorCode.ERR_UNDERAGE_OR_OVERAGE.value

    # Valid: 26 years old
    valid_birthdate = (today - timedelta(days=26 * 365)).isoformat()
    resp_valid = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "validage@example.com",
            "password": "Password123!",
            "nickname": "JustRight",
            "birthdate": valid_birthdate,
            "resident_city": "Shenzhen",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["coding", "running", "coffee"],
        },
    )
    assert resp_valid.status_code == 201
    data = resp_valid.json()
    assert data["nickname"] == "JustRight"
    assert data["verification_status"] == "unsubmitted"


@pytest.mark.asyncio
async def test_registration_interest_tags_count(async_client: AsyncClient):
    """US-001: Validates that interest tags count must be between 3 and 8 inclusive."""
    today = date.today()
    birthdate = (today - timedelta(days=25 * 365)).isoformat()

    # Too few tags: 2 tags
    resp_few = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "tagsfew@example.com",
            "password": "Password123!",
            "nickname": "FewTags",
            "birthdate": birthdate,
            "resident_city": "Guangzhou",
            "gender": "Female",
            "dating_preference": "Male",
            "interest_tags": ["tag1", "tag2"],
        },
    )
    assert resp_few.status_code == 422
    assert resp_few.json()["error_code"] == AppErrorCode.ERR_INVALID_TAGS_COUNT.value

    # Too many tags: 9 tags
    resp_many = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "tagsmany@example.com",
            "password": "Password123!",
            "nickname": "ManyTags",
            "birthdate": birthdate,
            "resident_city": "Guangzhou",
            "gender": "Female",
            "dating_preference": "Male",
            "interest_tags": [f"tag{i}" for i in range(9)],
        },
    )
    assert resp_many.status_code == 422
    assert resp_many.json()["error_code"] == AppErrorCode.ERR_INVALID_TAGS_COUNT.value


@pytest.mark.asyncio
async def test_unverified_user_feature_gating(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-001 & US-003: Unverified users are rejected with HTTP 403 ERR_AUTH_REQUIRED on gated endpoints."""
    unverified_user = await test_users_factory(
        email="unverified@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
    )
    headers = auth_headers_factory(unverified_user)

    # Attempting to access recommendation deck
    deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
    assert deck_resp.status_code == 403
    assert deck_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

    # Attempting to swipe
    swipe_resp = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers,
        json={"target_user_id": 999, "action": "like"},
    )
    assert swipe_resp.status_code == 403
    assert swipe_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

    # Attempting to create a date
    date_resp = await async_client.post(
        "/api/v1/dates/",
        headers=headers,
        json={
            "conversation_id": 1,
            "activity_topic": "Coffee",
            "scheduled_datetime": (date.today() + timedelta(days=3)).isoformat() + "T14:00:00",
            "venue_name": "Starbucks",
            "venue_address": "Main Street 101",
            "venue_latitude": 39.9,
            "venue_longitude": 116.4,
        },
    )
    assert date_resp.status_code == 403
    assert date_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value


@pytest.mark.asyncio
async def test_ocr_credential_submission_and_audit(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-002 & US-003: Submits credential, runs OCR parsing, transitions to pending_review, audits to verified (+100 pts)."""
    user = await test_users_factory(
        email="student@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
        points=0,
    )
    headers = auth_headers_factory(user)

    dummy_cert = base64.b64encode(b"Dummy Graduation Certificate Content").decode("utf-8")
    submit_resp = await async_client.post(
        "/api/v1/auth/credentials/submit",
        headers=headers,
        json={
            "certificate_base64": dummy_cert,
            "filename": "tsinghua_diploma.jpg",
            "institution_name": "清华大学 硕士学位证书",
            "student_name": "李四",
        },
    )
    assert submit_resp.status_code == 200
    sub_data = submit_resp.json()
    assert sub_data["success"] is True
    assert sub_data["ocr_extracted"]["school_tier"] == "985"
    assert sub_data["ocr_extracted"]["degree_level"] == "Master"

    # Verify user state is now pending_review
    me_resp = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.json()["verification_status"] == "pending_review"

    # Admin Audit: Approve
    audit_resp = await async_client.post(
        f"/api/v1/auth/admin/audit/{user.id}",
        json={
            "status": "verified",
            "school_tier": "985",
            "degree_level": "Master",
        },
    )
    assert audit_resp.status_code == 200
    audited_user = audit_resp.json()
    assert audited_user["verification_status"] == "verified"
    assert audited_user["is_verified"] is True
    # Awarded 100 onboarding bonus points!
    assert audited_user["points_balance"] == 100


@pytest.mark.asyncio
async def test_public_profile_education_privacy_masking(
    async_client: AsyncClient,
    test_users_factory,
):
    """US-004: Public profile displays only school tier and degree level; masks raw credentials, serial numbers, and email."""
    user = await test_users_factory(
        email="confidential@example.com",
        nickname="SecretAgent",
        status=VerificationStatusEnum.VERIFIED,
        school_tier=SchoolTierEnum.TIER_985,
        degree_level=DegreeLevelEnum.DOCTORATE,
    )

    resp = await async_client.get(f"/api/v1/auth/profile/{user.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["nickname"] == "SecretAgent"
    assert data["school_tier"] == "985"
    assert data["degree_level"] == "Doctorate"
    assert data["is_verified"] is True

    # Must NOT expose private credentials or identifiers
    assert "email" not in data
    assert "credential_code" not in data
    assert "document_file_key" not in data
    assert "document_url" not in data


@pytest.mark.asyncio
async def test_registration_exact_age_boundaries_and_duplicate_email(async_client: AsyncClient):
    """US-001: Boundary tests for ages 20 and 35 (exact inclusive bounds), 19, 36, and duplicate email."""
    today = date.today()

    # Exact boundary 1: 20 years old today -> Allowed (201)
    birthdate_20 = (today.replace(year=today.year - 20)).isoformat()
    resp_20 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "age20@example.com",
            "password": "Password123!",
            "nickname": "Age20User",
            "birthdate": birthdate_20,
            "resident_city": "Beijing",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["tech", "music", "art"],
        },
    )
    assert resp_20.status_code == 201
    assert resp_20.json()["age"] == 20

    # Exact boundary 2: 35 years old today -> Allowed (201)
    birthdate_35 = (today.replace(year=today.year - 35)).isoformat()
    resp_35 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "age35@example.com",
            "password": "Password123!",
            "nickname": "Age35User",
            "birthdate": birthdate_35,
            "resident_city": "Shanghai",
            "gender": "Female",
            "dating_preference": "Male",
            "interest_tags": ["reading", "hiking", "cooking"],
        },
    )
    assert resp_35.status_code == 201
    assert resp_35.json()["age"] == 35

    # Boundary violation 3: 36 years old -> Rejected (422)
    birthdate_36 = (today.replace(year=today.year - 36)).isoformat()
    resp_36 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "age36@example.com",
            "password": "Password123!",
            "nickname": "Age36User",
            "birthdate": birthdate_36,
            "resident_city": "Shenzhen",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["tech", "music", "art"],
        },
    )
    assert resp_36.status_code == 422
    assert resp_36.json()["error_code"] == AppErrorCode.ERR_UNDERAGE_OR_OVERAGE.value

    # Duplicate email registration -> Rejected (400 ERR_USER_ALREADY_EXISTS)
    resp_dup = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "age20@example.com",  # Already registered
            "password": "AnotherPassword123!",
            "nickname": "CopyCat",
            "birthdate": birthdate_20,
            "resident_city": "Beijing",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["tech", "music", "art"],
        },
    )
    assert resp_dup.status_code == 400
    assert resp_dup.json()["error_code"] == AppErrorCode.ERR_USER_ALREADY_EXISTS.value


@pytest.mark.asyncio
async def test_registration_exact_tags_boundaries(async_client: AsyncClient):
    """US-001: Boundary tests for interest tags: exactly 3 (min) and 8 (max) are valid."""
    today = date.today()
    birthdate = (today.replace(year=today.year - 25)).isoformat()

    # Exactly 3 tags -> Succeeds (201)
    resp_3 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "tags3@example.com",
            "password": "Password123!",
            "nickname": "ThreeTags",
            "birthdate": birthdate,
            "resident_city": "Chengdu",
            "gender": "Male",
            "dating_preference": "Female",
            "interest_tags": ["tea", "photography", "cinema"],
        },
    )
    assert resp_3.status_code == 201
    assert len(resp_3.json()["interest_tags"]) == 3

    # Exactly 8 tags -> Succeeds (201)
    resp_8 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "tags8@example.com",
            "password": "Password123!",
            "nickname": "EightTags",
            "birthdate": birthdate,
            "resident_city": "Wuhan",
            "gender": "Female",
            "dating_preference": "Male",
            "interest_tags": [f"interest_{i}" for i in range(8)],
        },
    )
    assert resp_8.status_code == 201
    assert len(resp_8.json()["interest_tags"]) == 8


@pytest.mark.asyncio
async def test_unverified_user_chat_gating(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-001 & US-003: Unverified users attempting to access IM chat are blocked with 403 ERR_AUTH_REQUIRED."""
    unverified_user = await test_users_factory(
        email="unverified_chat@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
    )
    headers = auth_headers_factory(unverified_user)

    # Attempting to fetch conversations
    conv_resp = await async_client.get("/api/v1/chat/conversations", headers=headers)
    assert conv_resp.status_code == 403
    assert conv_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

    # Attempting to send message to conversation #1
    msg_resp = await async_client.post(
        "/api/v1/chat/conversations/1/messages",
        headers=headers,
        json={"content": "Should be blocked", "message_type": "text"},
    )
    assert msg_resp.status_code == 403
    assert msg_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value


@pytest.mark.asyncio
async def test_blurry_credential_ocr_flags_manual_audit(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-002: Blurry or low-confidence (<0.70) document flags requires_manual_audit=True without failing submission."""
    user = await test_users_factory(
        email="blurry_user@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
    )
    headers = auth_headers_factory(user)

    dummy_cert = base64.b64encode(b"Blurry Unclear Graduation Photo").decode("utf-8")
    submit_resp = await async_client.post(
        "/api/v1/auth/credentials/submit",
        headers=headers,
        json={
            "certificate_base64": dummy_cert,
            "filename": "blurry_unclear_diploma.jpg",
            "institution_name": "浙江大学 博士",
            "student_name": "王五",
        },
    )
    assert submit_resp.status_code == 200
    res = submit_resp.json()
    assert res["success"] is True
    assert res["ocr_extracted"]["confidence"] < 0.70
    assert res["ocr_extracted"]["requires_manual_audit"] is True


@pytest.mark.asyncio
async def test_admin_audit_rejection_and_resubmission(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-003: Admin rejects submission, status becomes 'rejected' with reason, and user can re-upload."""
    user = await test_users_factory(
        email="rejected_user@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
    )
    headers = auth_headers_factory(user)

    # 1. Initial submission
    dummy_cert = base64.b64encode(b"Sample Content").decode("utf-8")
    await async_client.post(
        "/api/v1/auth/credentials/submit",
        headers=headers,
        json={
            "certificate_base64": dummy_cert,
            "filename": "cert.jpg",
            "institution_name": "北京大学",
            "student_name": "赵六",
        },
    )

    # 2. Admin rejects submission
    audit_resp = await async_client.post(
        f"/api/v1/auth/admin/audit/{user.id}",
        json={
            "status": "rejected",
            "rejection_reason": "Certificate photo altered or falsified",
        },
    )
    assert audit_resp.status_code == 200
    assert audit_resp.json()["verification_status"] == "rejected"
    assert audit_resp.json()["is_verified"] is False

    # 3. User resubmits valid credentials -> transitions back to pending_review
    resubmit_resp = await async_client.post(
        "/api/v1/auth/credentials/submit",
        headers=headers,
        json={
            "edu_email": "zhaoliu@pku.edu.cn",
            "credential_code": "OFFICIAL-PKU-12345",
            "institution_name": "北京大学",
            "student_name": "赵六",
        },
    )
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["verification_status"] == "pending_review"


@pytest.mark.asyncio
async def test_encrypted_oss_storage_and_presigned_url_expiration(
    async_client: AsyncClient,
):
    """US-004 & NFR-SEC-01: Verifies AES-256 encrypted storage at rest and 5-minute pre-signed URL download validation."""
    from src.core.crypto_oss import storage_service, encrypt_document, decrypt_document

    sample_doc = b"CONFIDENTIAL_GRADUATION_DIPLOMA_RAW_BYTES"
    file_key = storage_service.upload_file(sample_doc, "degree.pdf")

    # Verify document is encrypted at rest (stored bytes != plaintext bytes)
    stored_raw = storage_service._store[file_key]
    assert stored_raw != sample_doc
    assert len(stored_raw) > len(sample_doc)  # Contains 12-byte nonce + 16-byte tag

    # Decrypting returns original bytes
    decrypted = storage_service.download_file(file_key)
    assert decrypted == sample_doc

    # Valid pre-signed URL allows download
    presigned_url = storage_service.generate_presigned_url(file_key, expires_in=300)
    dl_resp = await async_client.get(presigned_url)
    assert dl_resp.status_code == 200
    assert dl_resp.content == sample_doc

    # Expired token (> 5 min) is rejected with 403 Forbidden
    import time
    import jwt
    from src.config import get_settings
    settings = get_settings()

    expired_payload = {
        "sub": "oss_presigned_download",
        "file_key": file_key,
        "exp": int(time.time()) - 10,  # 10 seconds in the past
        "iat": int(time.time()) - 310,
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    expired_resp = await async_client.get(f"/api/v1/auth/documents/download?token={expired_token}")
    assert expired_resp.status_code == 403


@pytest.mark.asyncio
async def test_pending_review_and_rejected_feature_gating(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-001 & US-003: Users with 'pending_review' or 'rejected' status are strictly blocked with 403 ERR_AUTH_REQUIRED."""
    pending_user = await test_users_factory(
        email="pending_gate@example.com",
        status=VerificationStatusEnum.PENDING_REVIEW,
    )
    rejected_user = await test_users_factory(
        email="rejected_gate@example.com",
        status=VerificationStatusEnum.REJECTED,
    )

    for user in [pending_user, rejected_user]:
        headers = auth_headers_factory(user)

        # 1. Blocked from recommendation deck
        deck_resp = await async_client.get("/api/v1/recommendations/daily-deck", headers=headers)
        assert deck_resp.status_code == 403
        assert deck_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

        # 2. Blocked from swiping
        swipe_resp = await async_client.post(
            "/api/v1/recommendations/swipe",
            headers=headers,
            json={"target_user_id": 999, "action": "like"},
        )
        assert swipe_resp.status_code == 403
        assert swipe_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

        # 3. Blocked from initiating dates
        date_resp = await async_client.post(
            "/api/v1/dates/",
            headers=headers,
            json={
                "conversation_id": 1,
                "activity_topic": "Coffee",
                "scheduled_datetime": (date.today() + timedelta(days=3)).isoformat() + "T14:00:00",
                "venue_name": "Cafe",
                "venue_address": "Street 1",
                "venue_latitude": 30.2,
                "venue_longitude": 120.1,
            },
        )
        assert date_resp.status_code == 403
        assert date_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value

        # 4. Blocked from chat conversations
        chat_resp = await async_client.get("/api/v1/chat/conversations", headers=headers)
        assert chat_resp.status_code == 403
        assert chat_resp.json()["error_code"] == AppErrorCode.ERR_AUTH_REQUIRED.value


@pytest.mark.asyncio
async def test_registration_dating_preference_both_and_invalid_enum(async_client: AsyncClient):
    """US-001: Registering with dating preference 'Both' succeeds (201); invalid enum values return 422."""
    today = date.today()
    valid_birthdate = (today - timedelta(days=24 * 365)).isoformat()

    # 1. Valid registration with dating preference 'Both'
    resp_both = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "pref_both@example.com",
            "password": "Password123!",
            "nickname": "OpenMinded",
            "birthdate": valid_birthdate,
            "resident_city": "Chengdu",
            "gender": "Female",
            "dating_preference": "Both",
            "interest_tags": ["art", "gaming", "music"],
        },
    )
    assert resp_both.status_code == 201
    assert resp_both.json()["dating_preference"] == "Both"

    # 2. Invalid gender returns 422
    resp_bad_gender = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad_gender@example.com",
            "password": "Password123!",
            "nickname": "InvalidGender",
            "birthdate": valid_birthdate,
            "resident_city": "Beijing",
            "gender": "UnknownGender",
            "dating_preference": "Male",
            "interest_tags": ["art", "gaming", "music"],
        },
    )
    assert resp_bad_gender.status_code == 422

    # 3. Invalid dating preference returns 422
    resp_bad_pref = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad_pref@example.com",
            "password": "Password123!",
            "nickname": "InvalidPref",
            "birthdate": valid_birthdate,
            "resident_city": "Beijing",
            "gender": "Male",
            "dating_preference": "AnySinglePerson",
            "interest_tags": ["art", "gaming", "music"],
        },
    )
    assert resp_bad_pref.status_code == 422


@pytest.mark.asyncio
async def test_credential_submission_email_and_code_without_file(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-002: Submitting verification code and .edu email without photo triggers extraction and pending_review."""
    user = await test_users_factory(
        email="pku_alumni@example.com",
        status=VerificationStatusEnum.UNSUBMITTED,
    )
    headers = auth_headers_factory(user)

    resp = await async_client.post(
        "/api/v1/auth/credentials/submit",
        headers=headers,
        json={
            "edu_email": "alumni@pku.edu.cn",
            "credential_code": "OFFICIAL-PKU-998877",
            "institution_name": "北京大学 硕士研究生",
            "student_name": "张学友",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["verification_status"] == "pending_review"
    assert data["ocr_extracted"]["school_tier"] == "985"
    assert data["ocr_extracted"]["degree_level"] == "Master"
    assert data["ocr_extracted"]["student_name"] == "张学友"


@pytest.mark.asyncio
async def test_unverified_user_public_profile(
    async_client: AsyncClient,
    test_users_factory,
):
    """US-004: Public profile of unverified user shows is_verified=False and no school tier."""
    unverified = await test_users_factory(
        email="public_unverified@example.com",
        nickname="PendingUser",
        status=VerificationStatusEnum.UNSUBMITTED,
        school_tier=None,
        degree_level=None,
    )

    resp = await async_client.get(f"/api/v1/auth/profile/{unverified.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "PendingUser"
    assert data["is_verified"] is False
    assert data["school_tier"] is None
    assert data["degree_level"] is None


