"""1v1 instant messaging lifecycle, WebSocket dispatch, and 7-day 0-message circuit breaker."""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.matching import Match, MatchStatusEnum
from src.models.chat import (
    Conversation,
    ChatMessage,
    ConversationStatusEnum,
    MessageTypeEnum,
)
from src.core.exceptions import (
    MatchExpiredException,
    AppBaseException,
    AppErrorCode,
)
from src.schemas.chat_schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ConversationResponse,
)
from src.schemas.user_schemas import UserPublicProfileResponse
from src.services.websocket_manager import ws_manager


class ChatService:
    """Manages chat sessions, real-time message forwarding, and circuit-breaker triggers."""

    @classmethod
    async def create_conversation(
        cls,
        db: AsyncSession,
        match_id: int,
        user_a_id: int,
        user_b_id: int,
    ) -> Conversation:
        """Initializes 1v1 conversation session for a new match."""
        conv = Conversation(
            match_id=match_id,
            user_a_id=user_a_id,
            user_b_id=user_b_id,
            status=ConversationStatusEnum.ACTIVE,
            message_count=0,
            created_at=datetime.utcnow(),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    @classmethod
    async def send_message(
        cls,
        db: AsyncSession,
        conversation_id: int,
        sender_id: int,
        req: ChatMessageCreateRequest,
    ) -> ChatMessage:
        """Dispatches a message inside an active conversation."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        conv = (await db.execute(stmt)).scalar_one_or_none()

        if not conv:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Conversation not found.",
            )

        # Check circuit breaker / expiration
        if conv.status == ConversationStatusEnum.ARCHIVED_INACTIVE:
            raise MatchExpiredException()

        # Sender must be participant
        if sender_id not in (conv.user_a_id, conv.user_b_id):
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="You are not authorized to send messages in this conversation.",
            )

        now = datetime.utcnow()
        msg = ChatMessage(
            conversation_id=conv.id,
            sender_id=sender_id,
            message_type=req.message_type,
            content=req.content,
            is_read=False,
            created_at=now,
        )
        db.add(msg)

        # Update conversation stats
        conv.message_count += 1
        conv.last_message_at = now

        await db.commit()
        await db.refresh(msg)

        # Real-time WebSocket delivery to recipient (<300ms)
        recipient_id = conv.user_b_id if sender_id == conv.user_a_id else conv.user_a_id
        await ws_manager.send_personal_message(
            message={
                "event": "new_message",
                "data": {
                    "id": msg.id,
                    "conversation_id": conv.id,
                    "sender_id": msg.sender_id,
                    "message_type": msg.message_type.value,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                },
            },
            user_id=recipient_id,
        )

        return msg

    @classmethod
    async def get_conversation_messages(
        cls,
        db: AsyncSession,
        conversation_id: int,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatMessageResponse]:
        """Fetches chronological messages in a conversation and marks unread as read."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if not conv or user_id not in (conv.user_a_id, conv.user_b_id):
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Conversation not found or access denied.",
            )

        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        messages = (await db.execute(msg_stmt)).scalars().all()

        # Mark other participant's messages as read
        unread_stmt = (
            update(ChatMessage)
            .where(
                and_(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.sender_id != user_id,
                    ChatMessage.is_read.is_(False),
                )
            )
            .values(is_read=True)
        )
        await db.execute(unread_stmt)
        await db.commit()

        return [
            ChatMessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_id=m.sender_id,
                message_type=m.message_type,
                content=m.content,
                is_read=m.is_read,
                created_at=m.created_at,
            )
            for m in messages
        ]

    @classmethod
    async def execute_circuit_breaker_check(
        cls,
        db: AsyncSession,
        threshold_days: int = 7,
    ) -> int:
        """Scheduled job: archives conversations and dissolves matches with 0 messages after 7 days."""
        cutoff = datetime.utcnow() - timedelta(days=threshold_days)

        # Select conversations created before cutoff with 0 messages and ACTIVE status
        stmt = select(Conversation).where(
            and_(
                Conversation.status == ConversationStatusEnum.ACTIVE,
                Conversation.created_at <= cutoff,
                Conversation.message_count == 0,
            )
        )
        expired_convs = (await db.execute(stmt)).scalars().all()
        dissolved_count = 0

        now = datetime.utcnow()
        for conv in expired_convs:
            conv.status = ConversationStatusEnum.ARCHIVED_INACTIVE

            # Dissolve associated match
            match_stmt = select(Match).where(Match.id == conv.match_id)
            match = (await db.execute(match_stmt)).scalar_one_or_none()
            if match and match.status == MatchStatusEnum.ACTIVE:
                match.status = MatchStatusEnum.DISSOLVED
                match.dissolved_at = now
                match.dissolution_reason = "7_days_inactivity_circuit_breaker"

            dissolved_count += 1

        await db.commit()
        return dissolved_count
