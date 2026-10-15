"""User onboarding, age calculation, tag validation, credential submission, and state machine transitions."""

import base64
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.models.user import (
    User,
    EducationCredential,
    VerificationStatusEnum,
    SchoolTierEnum,
    DegreeLevelEnum,
)
from src.models.points import PointReasonEnum
from src.schemas.user_schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    EducationSubmissionRequest,
    VerificationAuditRequest,
    TokenResponse,
)
from src.core.security import hash_password, verify_password, create_access_token
from src.core.crypto_oss import storage_service
from src.core.exceptions import AppBaseException, AppErrorCode
from src.services.ocr_service import OCRService
from src.services.points_service import PointsService
from src.config import get_settings

settings = get_settings()


class AuthService:
    """Manages user registration, authentication, credential uploads, and audit lifecycles."""

    @classmethod
    async def register_user(
        cls,
        db: AsyncSession,
        req: UserRegisterRequest,
    ) -> User:
        """Creates user profile with unsubmitted verification status."""
        stmt = select(User).where(User.email == req.email)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_USER_ALREADY_EXISTS,
                message="An account with this email address already exists.",
            )

        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            nickname=req.nickname,
            birthdate=req.birthdate,
            resident_city=req.resident_city,
            gender=req.gender,
            dating_preference=req.dating_preference,
            interest_tags=req.interest_tags,
            verification_status=VerificationStatusEnum.UNSUBMITTED,
            points_balance=0,
            reputation_score=3.5,
            reputation_count=0,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @classmethod
    async def authenticate_user(
        cls,
        db: AsyncSession,
        req: UserLoginRequest,
    ) -> TokenResponse:
        """Validates credentials and returns JWT token."""
        stmt = select(User).where(User.email == req.email)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user or not verify_password(req.password, user.hashed_password):
            raise AppBaseException(
                status_code=401,
                error_code=AppErrorCode.ERR_INVALID_CREDENTIALS,
                message="Invalid email or password.",
            )

        token = create_access_token(data={"sub": str(user.id), "email": user.email})
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
        )

    @classmethod
    async def submit_education_credential(
        cls,
        db: AsyncSession,
        user: User,
        req: EducationSubmissionRequest,
    ) -> EducationCredential:
        """Uploads encrypted credential document and executes OCR extraction."""
        file_key = None
        file_bytes = b""
        if req.certificate_base64:
            try:
                file_bytes = base64.b64decode(req.certificate_base64)
                file_key = storage_service.upload_file(file_bytes, req.filename or "doc.jpg")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to process certificate file: {str(e)}",
                )

        # Run OCR
        ocr_result = OCRService.parse_credential_document(
            file_bytes=file_bytes,
            filename=req.filename,
            student_name_hint=req.student_name,
            institution_hint=req.institution_name,
            credential_code=req.credential_code,
            edu_email=req.edu_email,
        )

        # Load or create EducationCredential record
        stmt = select(EducationCredential).where(EducationCredential.user_id == user.id)
        cred = (await db.execute(stmt)).scalar_one_or_none()

        if not cred:
            cred = EducationCredential(
                user_id=user.id,
                document_file_key=file_key,
                credential_code=req.credential_code,
                edu_email=req.edu_email,
                ocr_student_name=ocr_result.student_name,
                ocr_institution_name=ocr_result.institution_name,
                school_tier=ocr_result.school_tier,
                degree_level=ocr_result.degree_level,
                ocr_confidence=ocr_result.confidence,
                requires_manual_audit=ocr_result.requires_manual_audit,
                created_at=datetime.utcnow(),
            )
            db.add(cred)
        else:
            cred.document_file_key = file_key or cred.document_file_key
            cred.credential_code = req.credential_code or cred.credential_code
            cred.edu_email = req.edu_email or cred.edu_email
            cred.ocr_student_name = ocr_result.student_name
            cred.ocr_institution_name = ocr_result.institution_name
            cred.school_tier = ocr_result.school_tier
            cred.degree_level = ocr_result.degree_level
            cred.ocr_confidence = ocr_result.confidence
            cred.requires_manual_audit = ocr_result.requires_manual_audit
            cred.rejection_reason = None

        # Transition state machine to pending_review
        user.verification_status = VerificationStatusEnum.PENDING_REVIEW

        await db.commit()
        await db.refresh(cred)
        await db.refresh(user)
        return cred

    @classmethod
    async def audit_verification_status(
        cls,
        db: AsyncSession,
        user_id: int,
        req: VerificationAuditRequest,
    ) -> User:
        """Admin compliance audit transitioning user to verified or rejected."""
        stmt = select(User).where(User.id == user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="User not found.",
            )

        cred_stmt = select(EducationCredential).where(EducationCredential.user_id == user_id)
        cred = (await db.execute(cred_stmt)).scalar_one_or_none()

        if req.status == VerificationStatusEnum.VERIFIED:
            user.verification_status = VerificationStatusEnum.VERIFIED
            user.verified_at = datetime.utcnow()
            if cred:
                if req.school_tier:
                    cred.school_tier = req.school_tier
                if req.degree_level:
                    cred.degree_level = req.degree_level
                cred.requires_manual_audit = False

            # Award 100 onboarding bonus points atomically
            idempotency = f"onboarding_verified_bonus_{user.id}"
            await PointsService.award_points(
                db=db,
                user=user,
                amount=100,
                reason=PointReasonEnum.EDUCATION_VERIFIED,
                idempotency_key=idempotency,
                description="Education verification approval bonus",
            )
        elif req.status == VerificationStatusEnum.REJECTED:
            user.verification_status = VerificationStatusEnum.REJECTED
            if cred:
                cred.rejection_reason = req.rejection_reason or "Mismatched or invalid credentials"

        await db.commit()
        await db.refresh(user)
        return user
