"""Direct messaging, conversation inbox, icebreaker topics, and intimacy REST endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from soulred.api.deps import get_db_session, get_current_active_user
from soulred.models.chat import (
    ChatConversation,
    ChatMessage,
    IntimacyRecord,
    IntimacyLevelEnum,
)
from soulred.models.user import User
from soulred.schemas.chat import (
    ConversationSummaryResponse,
    MessageResponse,
    IcebreakerResponse,
    IntimacyStatusResponse,
    MessageRecallRequest,
)
from soulred.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Instant Messaging"])


@router.get(
    "/conversations",
    response_model=List[ConversationSummaryResponse],
    summary="List direct messaging conversations in user's inbox",
)
def list_conversations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[ConversationSummaryResponse]:
    """Retrieve all active conversations with peer user info, last message, and intimacy tier."""
    conversations = (
        db.query(ChatConversation)
        .filter(
            or_(
                ChatConversation.user_a_id == current_user.id,
                ChatConversation.user_b_id == current_user.id,
            )
        )
        .order_by(ChatConversation.last_message_at.desc().nullslast())
        .all()
    )

    summaries: List[ConversationSummaryResponse] = []
    for conv in conversations:
        peer_id = conv.user_b_id if conv.user_a_id == current_user.id else conv.user_a_id
        peer = db.query(User).filter(User.id == peer_id).first()
        if not peer:
            continue

        peer_profile = peer.profile
        peer_nickname = peer_profile.nickname if peer_profile else peer.username
        peer_avatar = peer_profile.avatar_url if peer_profile else None

        # Count unread messages
        unread_count = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False,
            )
            .count()
        )

        intimacy = conv.intimacy
        intimacy_level = intimacy.current_level if intimacy else "初识萌芽"
        intimacy_score = intimacy.intimacy_score if intimacy else 0.0

        summaries.append(
            ConversationSummaryResponse(
                conversation_id=conv.id,
                peer_user_id=peer.id,
                peer_nickname=peer_nickname,
                peer_avatar_url=peer_avatar,
                last_message=conv.last_message_content,
                last_message_at=conv.last_message_at,
                unread_count=unread_count,
                is_stranger_session=conv.is_stranger_session,
                intimacy_level=intimacy_level,
                intimacy_score=intimacy_score,
            )
        )

    return summaries


@router.get(
    "/history/{target_user_id}",
    response_model=List[MessageResponse],
    summary="Retrieve message history between current user and peer",
)
def get_chat_history(
    target_user_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[MessageResponse]:
    """Fetch chronological messages and mark incoming messages as read."""
    conv = (
        db.query(ChatConversation)
        .filter(
            or_(
                and_(ChatConversation.user_a_id == current_user.id, ChatConversation.user_b_id == target_user_id),
                and_(ChatConversation.user_a_id == target_user_id, ChatConversation.user_b_id == current_user.id),
            )
        )
        .first()
    )
    if not conv:
        return []

    messages = ChatService.get_conversation_history(
        db=db,
        conversation_id=conv.id,
        current_user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [MessageResponse.model_validate(m) for m in messages]


@router.get(
    "/icebreakers/{target_user_id}",
    response_model=IcebreakerResponse,
    summary="Get smart icebreaker conversation suggestions",
)
def get_icebreakers(
    target_user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> IcebreakerResponse:
    """Generate intelligent opening lines based on mutual MBTI and common interest tags."""
    return ChatService.generate_icebreakers(
        db=db,
        user_a_id=current_user.id,
        user_b_id=target_user_id,
    )


@router.get(
    "/intimacy/{target_user_id}",
    response_model=IntimacyStatusResponse,
    summary="Get Soul intimacy tree level and unlocked perks",
)
def get_intimacy_status(
    target_user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> IntimacyStatusResponse:
    """Retrieve intimacy XP progression, current level badge, and next tier requirement."""
    conv = (
        db.query(ChatConversation)
        .filter(
            or_(
                and_(ChatConversation.user_a_id == current_user.id, ChatConversation.user_b_id == target_user_id),
                and_(ChatConversation.user_a_id == target_user_id, ChatConversation.user_b_id == current_user.id),
            )
        )
        .first()
    )

    if not conv or not conv.intimacy:
        return IntimacyStatusResponse(
            conversation_id=conv.id if conv else "none",
            intimacy_score=0.0,
            current_level=IntimacyLevelEnum.SEED.value,
            next_level_xp=20.0,
            interaction_days=0,
            unlocked_perks=["基础纯文本打招呼"],
        )

    intimacy = conv.intimacy
    score = intimacy.intimacy_score

    # Determine next level threshold
    if score < 20.0:
        next_xp = 20.0
    elif score < 60.0:
        next_xp = 60.0
    elif score < 150.0:
        next_xp = 150.0
    else:
        next_xp = 150.0

    perks = list(intimacy.unlocked_badges or [])
    if score >= 20.0:
        perks.append("解锁专属气泡装扮")
    if score >= 60.0:
        perks.append("解锁合影挂件")
    if score >= 150.0:
        perks.append("挚友星辰守护徽章")

    return IntimacyStatusResponse(
        conversation_id=conv.id,
        intimacy_score=score,
        current_level=intimacy.current_level,
        next_level_xp=next_xp,
        interaction_days=intimacy.interaction_days,
        unlocked_perks=list(set(perks)),
    )


@router.post(
    "/recall",
    response_model=MessageResponse,
    summary="Recall a sent message within 2 minutes",
)
def recall_message(
    recall_in: MessageRecallRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Enforce strict 2-minute message recall window."""
    recalled = ChatService.recall_message(
        db=db,
        message_id=recall_in.message_id,
        user_id=current_user.id,
    )
    return MessageResponse.model_validate(recalled)
