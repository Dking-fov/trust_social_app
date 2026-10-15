"""Offline date workflow, POI invitations, 24h expiration, cancellation rules, dynamic QR, and GPS check-in."""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import pyotp
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User
from src.models.chat import Conversation, ChatMessage, MessageTypeEnum
from src.models.dating import (
    DateInvitation,
    DateCheckIn,
    DateStatusEnum,
    CheckInMethodEnum,
)
from src.models.points import PointReasonEnum
from src.core.anti_spoofing import LocationProofValidator, DeviceIntegrityHeaders
from src.core.exceptions import (
    AppBaseException,
    AppErrorCode,
    GeoSpoofingException,
)
from src.schemas.dating_schemas import (
    DateInviteCreateRequest,
    DateCheckInQRGenerateResponse,
    DateCheckInGPSRequest,
)
from src.services.points_service import PointsService
from src.services.websocket_manager import ws_manager

settings = get_settings()


class DatingService:
    """Orchestrates structured date proposals, arrival check-in validation, and penalty execution."""

    @classmethod
    async def create_date_invitation(
        cls,
        db: AsyncSession,
        initiator: User,
        req: DateInviteCreateRequest,
    ) -> DateInvitation:
        """Proposes structured date invitation inside an active 1v1 conversation."""
        conv_stmt = select(Conversation).where(Conversation.id == req.conversation_id)
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()

        if not conv or initiator.id not in (conv.user_a_id, conv.user_b_id):
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Conversation not found or access denied.",
            )

        recipient_id = conv.user_b_id if initiator.id == conv.user_a_id else conv.user_a_id

        # Generate TOTP secret for dynamic QR check-ins
        totp_secret = pyotp.random_base32()

        invitation = DateInvitation(
            conversation_id=conv.id,
            initiator_id=initiator.id,
            recipient_id=recipient_id,
            activity_topic=req.activity_topic,
            scheduled_datetime=req.scheduled_datetime,
            venue_name=req.venue_name,
            venue_address=req.venue_address,
            venue_latitude=req.venue_latitude,
            venue_longitude=req.venue_longitude,
            status=DateStatusEnum.PENDING_ACCEPTANCE,
            totp_secret=totp_secret,
            created_at=datetime.utcnow(),
        )
        db.add(invitation)
        await db.flush()

        # Render Date Invitation card as a message in the chat
        invite_card_msg = ChatMessage(
            conversation_id=conv.id,
            sender_id=initiator.id,
            message_type=MessageTypeEnum.DATE_INVITE,
            content=f"Proposed Date: {req.activity_topic} at {req.venue_name} on {req.scheduled_datetime.strftime('%Y-%m-%d %H:%M')}",
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(invite_card_msg)
        conv.message_count += 1
        conv.last_message_at = datetime.utcnow()

        await db.commit()
        await db.refresh(invitation)

        # Notify recipient via WebSocket
        await ws_manager.send_personal_message(
            message={
                "event": "date_invite_received",
                "data": {
                    "date_id": invitation.id,
                    "activity_topic": invitation.activity_topic,
                    "venue_name": invitation.venue_name,
                    "scheduled_datetime": invitation.scheduled_datetime.isoformat(),
                },
            },
            user_id=recipient_id,
        )

        return invitation

    @classmethod
    async def respond_to_invitation(
        cls,
        db: AsyncSession,
        user: User,
        date_id: int,
        action: str,  # "accept" or "decline"
    ) -> DateInvitation:
        """Recipient accepts or declines date proposal within 24-hour response window."""
        stmt = select(DateInvitation).where(DateInvitation.id == date_id)
        invitation = (await db.execute(stmt)).scalar_one_or_none()

        if not invitation:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Date invitation not found.",
            )

        if user.id != invitation.recipient_id:
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="Only the designated recipient can respond to this date proposal.",
            )

        if invitation.status != DateStatusEnum.PENDING_ACCEPTANCE:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message=f"Date is not pending acceptance (current status: {invitation.status}).",
            )

        # Check 24-hour expiration
        if (datetime.utcnow() - invitation.created_at) > timedelta(hours=24):
            invitation.status = DateStatusEnum.EXPIRED
            await db.commit()
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Date invitation has expired (24h response limit exceeded).",
            )

        if action.lower() == "accept":
            invitation.status = DateStatusEnum.CONFIRMED_PENDING_ARRIVAL
        else:
            invitation.status = DateStatusEnum.EXPIRED

        await db.commit()
        await db.refresh(invitation)

        # Broadcast update to initiator
        await ws_manager.send_personal_message(
            message={
                "event": "date_status_update",
                "data": {"date_id": invitation.id, "new_status": invitation.status.value},
            },
            user_id=invitation.initiator_id,
        )

        return invitation

    @classmethod
    async def cancel_date(
        cls,
        db: AsyncSession,
        user: User,
        date_id: int,
        reason: Optional[str] = None,
    ) -> DateInvitation:
        """Cancels confirmed date. Penalty-free if >=4h before meeting; penalized if <4h."""
        stmt = select(DateInvitation).where(DateInvitation.id == date_id)
        invitation = (await db.execute(stmt)).scalar_one_or_none()

        if not invitation:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Date not found.",
            )

        if user.id not in (invitation.initiator_id, invitation.recipient_id):
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="You are not authorized to cancel this date.",
            )

        if invitation.status != DateStatusEnum.CONFIRMED_PENDING_ARRIVAL:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Only confirmed pending dates can be cancelled.",
            )

        now = datetime.utcnow()
        time_to_meeting = invitation.scheduled_datetime - now
        invitation.cancelled_by_user_id = user.id
        invitation.cancellation_reason = reason

        if time_to_meeting >= timedelta(hours=settings.CANCELLATION_FREE_WINDOW_HOURS):
            # Penalty-free cancellation
            invitation.status = DateStatusEnum.CANCELLED_EXCUSED
        else:
            # Late cancellation penalty
            invitation.status = DateStatusEnum.NO_SHOW
            invitation.no_show_user_id = user.id

            # Deduct 0.5 reputation and 50 points
            user.reputation_score = max(1.0, round(user.reputation_score - 0.5, 2))
            idempotency = f"late_cancellation_{invitation.id}_{user.id}"
            await PointsService.deduct_points(
                db=db,
                user=user,
                amount=50,
                reason=PointReasonEnum.NO_SHOW_PENALTY,
                idempotency_key=idempotency,
                description=f"Late cancellation penalty for date #{invitation.id}",
            )

        await db.commit()
        await db.refresh(invitation)
        return invitation

    @classmethod
    async def generate_dynamic_qr(
        cls,
        db: AsyncSession,
        user: User,
        date_id: int,
    ) -> DateCheckInQRGenerateResponse:
        """Generates dynamic TOTP token valid for 60 seconds."""
        stmt = select(DateInvitation).where(DateInvitation.id == date_id)
        invitation = (await db.execute(stmt)).scalar_one_or_none()

        if not invitation:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Date not found.",
            )

        if user.id not in (invitation.initiator_id, invitation.recipient_id):
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="Unauthorized.",
            )

        if invitation.status != DateStatusEnum.CONFIRMED_PENDING_ARRIVAL:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Date must be in confirmed pending arrival status to check in.",
            )

        secret = invitation.totp_secret or pyotp.random_base32()
        if not invitation.totp_secret:
            invitation.totp_secret = secret
            await db.commit()

        totp = pyotp.TOTP(secret, interval=settings.TOTP_STEP_SECONDS)
        current_token = totp.now()

        # Token embedded with date_id and generator user_id
        qr_payload = f"DATE_QR:{invitation.id}:{user.id}:{current_token}"
        expires_at = datetime.utcnow() + timedelta(seconds=settings.TOTP_STEP_SECONDS)

        return DateCheckInQRGenerateResponse(
            date_id=invitation.id,
            qr_token=qr_payload,
            valid_seconds=settings.TOTP_STEP_SECONDS,
            expires_at=expires_at,
        )

    @classmethod
    async def verify_qr_checkin(
        cls,
        db: AsyncSession,
        scanner_user: User,
        qr_token: str,
    ) -> DateInvitation:
        """Verifies scanned TOTP token. Mutual scanning certifies arrival and completes date."""
        try:
            parts = qr_token.split(":")
            if len(parts) != 4 or parts[0] != "DATE_QR":
                raise ValueError("Invalid QR payload format")
            date_id = int(parts[1])
            generator_user_id = int(parts[2])
            totp_code = parts[3]
        except Exception:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Invalid or malformed QR check-in token.",
            )

        stmt = select(DateInvitation).where(DateInvitation.id == date_id)
        invitation = (await db.execute(stmt)).scalar_one_or_none()
        if not invitation:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Date not found.",
            )

        if invitation.status != DateStatusEnum.CONFIRMED_PENDING_ARRIVAL:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Date is not awaiting arrival check-in.",
            )

        # Scanner and generator must be distinct participants in the date
        participants = {invitation.initiator_id, invitation.recipient_id}
        if {scanner_user.id, generator_user_id} != participants or scanner_user.id == generator_user_id:
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="QR scan must occur mutually between the two distinct date participants.",
            )

        # Verify TOTP code (valid for 60s, accepts +/- 1 window for network leeway)
        totp = pyotp.TOTP(invitation.totp_secret, interval=settings.TOTP_STEP_SECONDS)
        if not totp.verify(totp_code, valid_window=1):
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="QR code has expired or is invalid.",
            )

        # Both participants are verified!
        invitation.initiator_checked_in = True
        invitation.recipient_checked_in = True
        invitation.status = DateStatusEnum.COMPLETED
        invitation.completed_at = datetime.utcnow()

        # Log check-in events
        c1 = DateCheckIn(
            date_invitation_id=invitation.id,
            user_id=generator_user_id,
            method=CheckInMethodEnum.DYNAMIC_QR,
            verified_at=datetime.utcnow(),
        )
        c2 = DateCheckIn(
            date_invitation_id=invitation.id,
            user_id=scanner_user.id,
            method=CheckInMethodEnum.DYNAMIC_QR,
            verified_at=datetime.utcnow(),
        )
        db.add_all([c1, c2])

        await db.commit()
        await db.refresh(invitation)

        # Dispatch WebSocket completion event
        await ws_manager.broadcast_to_match(
            user_a_id=invitation.initiator_id,
            user_b_id=invitation.recipient_id,
            event="date_completed",
            data={"date_id": invitation.id, "method": "dynamic_qr"},
        )

        return invitation

    @classmethod
    async def verify_gps_checkin(
        cls,
        db: AsyncSession,
        user: User,
        date_id: int,
        req: DateCheckInGPSRequest,
        headers: Optional[DeviceIntegrityHeaders] = None,
    ) -> DateInvitation:
        """Checks in participant via 100m GPS geofencing and anti-spoofing verification."""
        stmt = select(DateInvitation).where(DateInvitation.id == date_id)
        invitation = (await db.execute(stmt)).scalar_one_or_none()

        if not invitation:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Date not found.",
            )

        if user.id not in (invitation.initiator_id, invitation.recipient_id):
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="Unauthorized.",
            )

        if invitation.status != DateStatusEnum.CONFIRMED_PENDING_ARRIVAL:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Date is not in confirmed pending arrival status.",
            )

        # Enforce anti-spoofing and geofence check (100m radius)
        payload_flags = {"is_mock": req.is_mock}
        within_geofence, distance = LocationProofValidator.validate_and_compute_distance(
            user_lat=req.latitude,
            user_lon=req.longitude,
            target_lat=invitation.venue_latitude,
            target_lon=invitation.venue_longitude,
            max_radius_meters=settings.GPS_GEOFENCE_RADIUS_METERS,
            headers=headers,
            payload_flags=payload_flags,
        )

        if not within_geofence:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message=f"GPS check-in failed: current location is {distance:.1f}m away (max {settings.GPS_GEOFENCE_RADIUS_METERS}m allowed).",
            )

        # Mark user checked in
        if user.id == invitation.initiator_id:
            invitation.initiator_checked_in = True
        else:
            invitation.recipient_checked_in = True

        log = DateCheckIn(
            date_invitation_id=invitation.id,
            user_id=user.id,
            method=CheckInMethodEnum.GPS_GEOFENCE,
            latitude=req.latitude,
            longitude=req.longitude,
            distance_meters=distance,
            verified_at=datetime.utcnow(),
        )
        db.add(log)

        # If both checked in, mark completed
        if invitation.initiator_checked_in and invitation.recipient_checked_in:
            invitation.status = DateStatusEnum.COMPLETED
            invitation.completed_at = datetime.utcnow()

            await ws_manager.broadcast_to_match(
                user_a_id=invitation.initiator_id,
                user_b_id=invitation.recipient_id,
                event="date_completed",
                data={"date_id": invitation.id, "method": "gps_geofence"},
            )

        await db.commit()
        await db.refresh(invitation)
        return invitation

    @classmethod
    async def process_no_show_penalties(
        cls,
        db: AsyncSession,
        grace_period_minutes: int = 60,
    ) -> int:
        """Scheduled task: identifies unexcused no-shows, applies -0.5 reputation and -50 points."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=grace_period_minutes)

        stmt = select(DateInvitation).where(
            and_(
                DateInvitation.status == DateStatusEnum.CONFIRMED_PENDING_ARRIVAL,
                DateInvitation.scheduled_datetime <= cutoff,
            )
        )
        pending_dates = (await db.execute(stmt)).scalars().all()
        penalized_count = 0

        for date_inv in pending_dates:
            # Determine which party did not check in
            offenders = []
            if not date_inv.initiator_checked_in:
                offenders.append(date_inv.initiator_id)
            if not date_inv.recipient_checked_in:
                offenders.append(date_inv.recipient_id)

            date_inv.status = DateStatusEnum.NO_SHOW

            for offender_id in offenders:
                user_stmt = select(User).where(User.id == offender_id)
                user = (await db.execute(user_stmt)).scalar_one_or_none()
                if user:
                    date_inv.no_show_user_id = user.id
                    user.reputation_score = max(1.0, round(user.reputation_score - 0.5, 2))

                    idempotency = f"no_show_penalty_{date_inv.id}_{user.id}"
                    await PointsService.deduct_points(
                        db=db,
                        user=user,
                        amount=50,
                        reason=PointReasonEnum.NO_SHOW_PENALTY,
                        idempotency_key=idempotency,
                        description=f"Unexcused no-show penalty for scheduled date #{date_inv.id}",
                    )
                    penalized_count += 1

        await db.commit()
        return penalized_count
