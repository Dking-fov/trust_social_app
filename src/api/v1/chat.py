"""HTTP and WebSocket endpoints for 1v1 real-time chat, message history, and conversation list."""

from typing import List, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db, AsyncSessionLocal
from src.models.user import User, VerificationStatusEnum
from src.models.chat import Conversation, ChatMessage
from src.schemas.chat_schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ConversationResponse,
)
from src.schemas.user_schemas import UserPublicProfileResponse
from src.core.security import require_verified_user, decode_access_token
from src.services.chat_service import ChatService
from src.services.websocket_manager import ws_manager

router = APIRouter(prefix="/chat", tags=["Instant Messaging & Chat"])


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations_endpoint(
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves all active or archived 1v1 conversations for the current verified user."""
    stmt = (
        select(Conversation)
        .where(
            or_(
                Conversation.user_a_id == current_user.id,
                Conversation.user_b_id == current_user.id,
            )
        )
        .order_by(Conversation.updated_at.desc())
    )
    conversations = (await db.execute(stmt)).scalars().all()

    responses: List[ConversationResponse] = []
    for conv in conversations:
        partner_id = conv.user_b_id if conv.user_a_id == current_user.id else conv.user_a_id
        partner_stmt = select(User).where(User.id == partner_id)
        partner = (await db.execute(partner_stmt)).scalar_one_or_none()

        if not partner:
            continue

        partner_dto = UserPublicProfileResponse(
            id=partner.id,
            nickname=partner.nickname,
            age=partner.age,
            resident_city=partner.resident_city,
            gender=partner.gender,
            interest_tags=partner.interest_tags,
            reputation_score=partner.reputation_score,
            reputation_count=partner.reputation_count,
            school_tier=partner.education_credential.school_tier if partner.education_credential else None,
            degree_level=partner.education_credential.degree_level if partner.education_credential else None,
            is_verified=partner.verification_status == VerificationStatusEnum.VERIFIED,
        )

        # Fetch last message
        last_msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg = (await db.execute(last_msg_stmt)).scalar_one_or_none()
        last_msg_dto = (
            ChatMessageResponse(
                id=last_msg.id,
                conversation_id=last_msg.conversation_id,
                sender_id=last_msg.sender_id,
                message_type=last_msg.message_type,
                content=last_msg.content,
                is_read=last_msg.is_read,
                created_at=last_msg.created_at,
            )
            if last_msg
            else None
        )

        # Count unread messages
        unread_stmt = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.conversation_id == conv.id,
                    ChatMessage.sender_id != current_user.id,
                    ChatMessage.is_read.is_(False),
                )
            )
        )
        unread_count = len((await db.execute(unread_stmt)).scalars().all())

        responses.append(
            ConversationResponse(
                id=conv.id,
                match_id=conv.match_id,
                partner=partner_dto,
                status=conv.status,
                message_count=conv.message_count,
                last_message=last_msg_dto,
                unread_count=unread_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )

    return responses


@router.get("/conversations/{conversation_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages_endpoint(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves message history for a conversation and marks unread messages as read."""
    return await ChatService.get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageResponse)
async def send_message_endpoint(
    conversation_id: int,
    req: ChatMessageCreateRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Sends a message in an active conversation. Dispatches real-time WebSocket frame to recipient."""
    msg = await ChatService.send_message(
        db=db,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        req=req,
    )
    return ChatMessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        message_type=msg.message_type,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


@router.websocket("/ws/{user_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
):
    """WebSocket endpoint maintaining live duplex connection for instant delivery (<300ms)."""
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process client ping/keepalive
            await websocket.send_json({"event": "ack", "data": {"received": data}})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
