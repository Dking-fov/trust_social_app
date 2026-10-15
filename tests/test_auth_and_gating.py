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
