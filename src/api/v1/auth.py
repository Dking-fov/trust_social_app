"""Endpoints for registration, login, credential upload, and admin verification status transitions."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User, VerificationStatusEnum, EducationCredential
from src.schemas.user_schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserPublicProfileResponse,
    UserProfilePrivateResponse,
    EducationSubmissionRequest,
    VerificationAuditRequest,
)
from src.core.security import get_current_user
from src.core.crypto_oss import storage_service
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Verification"])


@router.post("/register", response_model=UserProfilePrivateResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Registers new user profile and dating preferences."""
    user = await AuthService.register_user(db=db, req=req)
    return UserProfilePrivateResponse(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        age=user.age,
        birthdate=user.birthdate,
        resident_city=user.resident_city,
        gender=user.gender,
        dating_preference=user.dating_preference,
        interest_tags=user.interest_tags,
        verification_status=user.verification_status,
        reputation_score=user.reputation_score,
        reputation_count=user.reputation_count,
        points_balance=user.points_balance,
        is_verified=user.verification_status == VerificationStatusEnum.VERIFIED,
        school_tier=None,
        degree_level=None,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(
    req: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates user and returns JWT access token."""
    return await AuthService.authenticate_user(db=db, req=req)


@router.get("/me", response_model=UserProfilePrivateResponse)
async def get_me_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetches private profile details of current authenticated user."""
    cred_stmt = select(EducationCredential).where(EducationCredential.user_id == current_user.id)
    cred = (await db.execute(cred_stmt)).scalar_one_or_none()

    return UserProfilePrivateResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.nickname,
        age=current_user.age,
        birthdate=current_user.birthdate,
        resident_city=current_user.resident_city,
        gender=current_user.gender,
        dating_preference=current_user.dating_preference,
        interest_tags=current_user.interest_tags,
        verification_status=current_user.verification_status,
        reputation_score=current_user.reputation_score,
        reputation_count=current_user.reputation_count,
        points_balance=current_user.points_balance,
        is_verified=current_user.verification_status == VerificationStatusEnum.VERIFIED,
        school_tier=cred.school_tier if cred else None,
        degree_level=cred.degree_level if cred else None,
        created_at=current_user.created_at,
    )


@router.get("/profile/{user_id}", response_model=UserPublicProfileResponse)
async def get_public_profile_endpoint(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetches desensitized public user profile card (US-004 privacy-safe)."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    cred_stmt = select(EducationCredential).where(EducationCredential.user_id == user.id)
    cred = (await db.execute(cred_stmt)).scalar_one_or_none()

    return UserPublicProfileResponse(
        id=user.id,
        nickname=user.nickname,
        age=user.age,
        resident_city=user.resident_city,
        gender=user.gender,
        interest_tags=user.interest_tags,
        reputation_score=user.reputation_score,
        reputation_count=user.reputation_count,
        school_tier=cred.school_tier if cred else None,
        degree_level=cred.degree_level if cred else None,
        is_verified=user.verification_status == VerificationStatusEnum.VERIFIED,
    )


@router.post("/credentials/submit")
async def submit_credential_endpoint(
    req: EducationSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submits education credentials, uploads encrypted file to private OSS, and executes OCR."""
    cred = await AuthService.submit_education_credential(db=db, user=current_user, req=req)
    return {
        "success": True,
        "message": "Education credential submitted for audit.",
        "verification_status": current_user.verification_status,
        "ocr_extracted": {
            "student_name": cred.ocr_student_name,
            "institution_name": cred.ocr_institution_name,
            "school_tier": cred.school_tier,
            "degree_level": cred.degree_level,
            "confidence": cred.ocr_confidence,
            "requires_manual_audit": cred.requires_manual_audit,
        },
    }


@router.post("/admin/audit/{user_id}", response_model=UserProfilePrivateResponse)
async def audit_credential_endpoint(
    user_id: int,
    req: VerificationAuditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Compliance audit endpoint approving or rejecting credential submission."""
    user = await AuthService.audit_verification_status(db=db, user_id=user_id, req=req)
    cred_stmt = select(EducationCredential).where(EducationCredential.user_id == user.id)
    cred = (await db.execute(cred_stmt)).scalar_one_or_none()

    return UserProfilePrivateResponse(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        age=user.age,
        birthdate=user.birthdate,
        resident_city=user.resident_city,
        gender=user.gender,
        dating_preference=user.dating_preference,
        interest_tags=user.interest_tags,
        verification_status=user.verification_status,
        reputation_score=user.reputation_score,
        reputation_count=user.reputation_count,
        points_balance=user.points_balance,
        is_verified=user.verification_status == VerificationStatusEnum.VERIFIED,
        school_tier=cred.school_tier if cred else None,
        degree_level=cred.degree_level if cred else None,
        created_at=user.created_at,
    )


@router.get("/documents/download")
async def download_document_endpoint(
    token: str = Query(...),
):
    """Private OSS download simulation protected by 5-minute pre-signed JWT URL."""
    file_key = storage_service.verify_presigned_token(token)
    if not file_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pre-signed URL is invalid or expired (5-minute TTL exceeded).",
        )

    try:
        data = storage_service.download_file(file_key)
        return Response(content=data, media_type="application/octet-stream")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
