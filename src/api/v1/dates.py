"""Endpoints for in-chat date invitations, responses, cancellations, dynamic QR, and GPS check-ins."""

from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.schemas.dating_schemas import (
    DateInviteCreateRequest,
    DateInviteResponse,
    DateRespondRequest,
    DateCancelRequest,
    DateCheckInQRGenerateResponse,
    DateCheckInQRScanRequest,
    DateCheckInGPSRequest,
)
from src.core.security import require_verified_user
from src.core.anti_spoofing import DeviceIntegrityHeaders
from src.services.dating_service import DatingService

router = APIRouter(prefix="/dates", tags=["Offline Date Workflow & Verification"])


@router.post("/", response_model=DateInviteResponse)
async def create_date_endpoint(
    req: DateInviteCreateRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Proposes a structured offline date with activity topic, datetime, and public venue POI."""
    date_inv = await DatingService.create_date_invitation(
        db=db,
        initiator=current_user,
        req=req,
    )
    return date_inv


@router.post("/{date_id}/respond", response_model=DateInviteResponse)
async def respond_date_endpoint(
    date_id: int,
    req: DateRespondRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Recipient accepts or declines date proposal within 24 hours."""
    return await DatingService.respond_to_invitation(
        db=db,
        user=current_user,
        date_id=date_id,
        action=req.action,
    )


@router.post("/{date_id}/cancel", response_model=DateInviteResponse)
async def cancel_date_endpoint(
    date_id: int,
    req: DateCancelRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancels confirmed date. Penalty-free if >=4h before scheduled time; penalizes if <4h."""
    return await DatingService.cancel_date(
        db=db,
        user=current_user,
        date_id=date_id,
        reason=req.reason,
    )


@router.post("/{date_id}/checkin/qr/generate", response_model=DateCheckInQRGenerateResponse)
async def generate_qr_endpoint(
    date_id: int,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Generates a dynamic 60-second TOTP QR code for mutual offline check-in."""
    return await DatingService.generate_dynamic_qr(
        db=db,
        user=current_user,
        date_id=date_id,
    )


@router.post("/checkin/qr/scan", response_model=DateInviteResponse)
async def scan_qr_endpoint(
    req: DateCheckInQRScanRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Scans dynamic TOTP QR code presented by dating partner to certify physical arrival."""
    return await DatingService.verify_qr_checkin(
        db=db,
        scanner_user=current_user,
        qr_token=req.qr_token,
    )


@router.post("/{date_id}/checkin/gps", response_model=DateInviteResponse)
async def gps_checkin_endpoint(
    date_id: int,
    req: DateCheckInGPSRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
    x_mock_location: Optional[bool] = Header(default=False),
    x_is_emulator: Optional[bool] = Header(default=False),
    x_hook_detected: Optional[bool] = Header(default=False),
    x_device_signature: Optional[str] = Header(default=None),
):
    """Certifies physical arrival via 100m GPS geofencing and anti-spoofing defense."""
    headers = DeviceIntegrityHeaders(
        x_mock_location=x_mock_location,
        x_is_emulator=x_is_emulator,
        x_hook_detected=x_hook_detected,
        x_device_signature=x_device_signature,
    )
    return await DatingService.verify_gps_checkin(
        db=db,
        user=current_user,
        date_id=date_id,
        req=req,
        headers=headers,
    )
