"""Validates US-007, US-008: instant message delivery, real-time dispatch, 7-day 0-message circuit breaker dissolution, and ERR_MATCH_EXPIRED."""

from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import GenderEnum, DatingPreferenceEnum
from src.models.matching import Match, MatchStatusEnum
from src.models.chat import Conversation, ChatMessage, ConversationStatusEnum, MessageTypeEnum
from src.core.exceptions import AppErrorCode
from src.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_send_and_receive_chat_message(
    async_client: AsyncClient,
    test_users_factory,
    auth_headers_factory,
):
    """US-007: Sends text messages in an active 1v1 conversation, verifies delivery and unread status."""
    user_a = await test_users_factory(
        email="sender@example.com",
        nickname="Alice",
        gender=GenderEnum.FEMALE,
        preference=DatingPreferenceEnum.MALE,
    )
    user_b = await test_users_factory(
        email="receiver@example.com",
        nickname="Bob",
        gender=GenderEnum.MALE,
        preference=DatingPreferenceEnum.FEMALE,
    )
    headers_a = auth_headers_factory(user_a)
    headers_b = auth_headers_factory(user_b)

    # Establish mutual match
    await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_a,
        json={"target_user_id": user_b.id, "action": "like"},
    )
    match_resp = await async_client.post(
        "/api/v1/recommendations/swipe",
        headers=headers_b,
        json={"target_user_id": user_a.id, "action": "like"},
    )
    match_data = match_resp.json()
    assert match_data["is_match"] is True
    conv_id = match_data["conversation_id"]

    # User A sends a message to User B
    msg_resp = await async_client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=headers_a,
        json={"content": "Hello Bob! Nice to match with you.", "message_type": "text"},
    )
    assert msg_resp.status_code == 200
    msg_data = msg_resp.json()
    assert msg_data["conversation_id"] == conv_id
    assert msg_data["sender_id"] == user_a.id
    assert msg_data["content"] == "Hello Bob! Nice to match with you."
    assert msg_data["is_read"] is False

    # User B views conversations list
    convs_resp = await async_client.get("/api/v1/chat/conversations", headers=headers_b)
    assert convs_resp.status_code == 200
    convs = convs_resp.json()
    assert len(convs) == 1
    assert convs[0]["id"] == conv_id
    assert convs[0]["unread_count"] == 1
    assert convs[0]["partner"]["nickname"] == "Alice"

    # User B fetches message history -> marks unread as read
    history_resp = await async_client.get(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=headers_b,
    )
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 1
    assert history[0]["content"] == "Hello Bob! Nice to match with you."

    # User B checks unread count again -> now 0
    convs_resp2 = await async_client.get("/api/v1/chat/conversations", headers=headers_b)
    assert convs_resp2.json()[0]["unread_count"] == 0


@pytest.mark.asyncio
async def test_circuit_breaker_archives_inactive_match_after_7_days(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-008: Inactive match with 0 messages after 7 days is archived by circuit breaker; messaging returns ERR_MATCH_EXPIRED."""
    user_a = await test_users_factory(email="zombie_a@example.com")
    user_b = await test_users_factory(email="zombie_b@example.com")
    headers_a = auth_headers_factory(user_a)

    eight_days_ago = datetime.utcnow() - timedelta(days=8)

    # Directly create match and conversation with 0 messages 8 days ago
    match = Match(
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        status=MatchStatusEnum.ACTIVE,
        matched_at=eight_days_ago,
    )
    db_session.add(match)
    await db_session.flush()

    conv = Conversation(
        match_id=match.id,
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        status=ConversationStatusEnum.ACTIVE,
        message_count=0,
        created_at=eight_days_ago,
        updated_at=eight_days_ago,
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Run circuit breaker check
    dissolved = await ChatService.execute_circuit_breaker_check(db_session, threshold_days=7)
    assert dissolved >= 1

    # Check database state
    await db_session.refresh(conv)
    await db_session.refresh(match)
    assert conv.status == ConversationStatusEnum.ARCHIVED_INACTIVE
    assert match.status == MatchStatusEnum.DISSOLVED
    assert match.dissolution_reason == "7_days_inactivity_circuit_breaker"

    # User A tries to send a message to the archived conversation -> ERR_MATCH_EXPIRED
    resp = await async_client.post(
        f"/api/v1/chat/conversations/{conv.id}/messages",
        headers=headers_a,
        json={"content": "Anyone here?", "message_type": "text"},
    )
    assert resp.status_code == 410
    assert resp.json()["error_code"] == AppErrorCode.ERR_MATCH_EXPIRED.value


@pytest.mark.asyncio
async def test_active_chat_spares_circuit_breaker(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_users_factory,
    auth_headers_factory,
):
    """US-008: Conversation with >= 1 message exchanged is spared from circuit breaker dissolution."""
    user_a = await test_users_factory(email="active_a@example.com")
    user_b = await test_users_factory(email="active_b@example.com")
    headers_a = auth_headers_factory(user_a)

    eight_days_ago = datetime.utcnow() - timedelta(days=8)

    match = Match(
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        status=MatchStatusEnum.ACTIVE,
        matched_at=eight_days_ago,
    )
    db_session.add(match)
    await db_session.flush()

    conv = Conversation(
        match_id=match.id,
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        status=ConversationStatusEnum.ACTIVE,
        message_count=1,  # Active conversation with 1 message
        last_message_at=eight_days_ago + timedelta(hours=1),
        created_at=eight_days_ago,
        updated_at=eight_days_ago,
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Run circuit breaker check
    dissolved = await ChatService.execute_circuit_breaker_check(db_session, threshold_days=7)
    assert dissolved == 0

    await db_session.refresh(conv)
    await db_session.refresh(match)
    assert conv.status == ConversationStatusEnum.ACTIVE
    assert match.status == MatchStatusEnum.ACTIVE

    # Sending messages still works smoothly
    resp = await async_client.post(
        f"/api/v1/chat/conversations/{conv.id}/messages",
        headers=headers_a,
        json={"content": "Still chatting!", "message_type": "text"},
    )
    assert resp.status_code == 200
