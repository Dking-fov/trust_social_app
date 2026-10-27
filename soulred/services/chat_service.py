"""Instant messaging, AI icebreakers, intimacy progression, and message recall service.

Implements:
- AI-driven smart icebreaker topic generation based on mutual persona tags & MBTI
- Real-time message storage with stranger anti-harassment limits & text safety filtering
- Soul intimacy experience point (XP) progression state machine (Seed -> Bud -> Flower -> Star)
- Strict 2-minute message recall window enforcement
- Conversation history retrieval with unread message auto-clearing
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException, status

from soulred.models.chat import (
    ChatConversation,
    ChatMessage,
    IntimacyRecord,
    MessageTypeEnum,
    IntimacyLevelEnum,
)
from soulred.models.user import User, UserProfile
from soulred.schemas.chat import (
    IcebreakerResponse,
    IntimacyStatusResponse,
)
from soulred.services.matching_service import MatchingService
from soulred.services.safety_service import ContentSafetyService


class ChatService:
    """Core domain service for direct messaging and intimacy progression."""

    INTIMACY_THRESHOLDS = [
        (150.0, IntimacyLevelEnum.STAR.value, "star_companion"),
        (60.0, IntimacyLevelEnum.FLOWER.value, "flowering_bond"),
        (20.0, IntimacyLevelEnum.BUD.value, "budding_friend"),
        (0.0, IntimacyLevelEnum.SEED.value, "seed_sprout"),
    ]

    @classmethod
    def generate_icebreakers(
        cls,
        db: Session,
        user_a_id: str,
        user_b_id: str,
    ) -> IcebreakerResponse:
        """Dynamically generate intelligent conversation starter suggestions."""
        profile_a = db.query(UserProfile).filter(UserProfile.user_id == user_a_id).first()
        profile_b = db.query(UserProfile).filter(UserProfile.user_id == user_b_id).first()

        tags_a = set(profile_a.interest_tags or []) if profile_a else set()
        tags_b = set(profile_b.interest_tags or []) if profile_b else set()
        common_tags = list(tags_a.intersection(tags_b))

        mbti_a = profile_a.mbti if profile_a else None
        mbti_b = profile_b.mbti if profile_b else None

        suggestions: List[str] = []

        # 1. Topic-driven suggestions
        if "艺术展览" in common_tags or "摄影" in common_tags:
            suggestions.append("你们都喜欢看展和视觉艺术，聊聊最近印象深刻的展览吧！")
        if "民谣音乐" in common_tags or "音乐节" in common_tags:
            suggestions.append("你们都喜欢现场音乐，最近常单曲循环哪首歌呢？")
        if "户外徒步" in common_tags or "露营" in common_tags:
            suggestions.append("好巧！你们都是户外探索爱好者，周末有什么逃离城市计划吗？")

        for tag in common_tags:
            topic_prompt = f"好巧，你们的资料都标记了 #{tag}，平时在这个爱好上有什么独家心得吗？"
            if topic_prompt not in suggestions:
                suggestions.append(topic_prompt)

        # 2. MBTI-driven suggestions
        if mbti_a and mbti_b:
            suggestions.append(
                f"{mbti_a} 与 {mbti_b} 相遇！听说你们的性格契合度很高，打个招呼认识一下吧～"
            )

        # 3. High-EQ general fallback
        if len(suggestions) < 3:
            suggestions.extend([
                "Hi~ 看到你主页的生活切片很有审美，今天过得充实吗？",
                "很高兴在 SoulRed 与你连接！分享一下今天遇到的美好小事吧～",
                "被你的动态吸引过来了，平时闲暇时间最喜欢做些什么呢？",
            ])

        return IcebreakerResponse(
            suggestions=suggestions[:4],
            common_topics=common_tags,
            common_mbti=f"{mbti_a} & {mbti_b}" if mbti_a and mbti_b else None,
        )

    @classmethod
    def record_message(
        cls,
        db: Session,
        sender_id: str,
        receiver_id: str,
        content: str,
        message_type: str = "text",
        media_url: Optional[str] = None,
    ) -> ChatMessage:
        """Send and persist a chat message after stranger quota and safety validation."""
        # 1. Stranger Anti-Harassment Quota Validation
        can_send = MatchingService.check_stranger_message_limit(
            db=db,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
        )
        if not can_send:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="非双向心动陌生人每日仅可发送 1 条文本打招呼消息，且不可发送图片或语音。",
            )

        # 2. Real-time Content Safety Inspection
        safety_check = ContentSafetyService.check_text_safety(content)
        if safety_check["action"] == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="消息包含涉黄涉政或违规欺诈引流内容，已被系统风控拦截。",
            )

        clean_content = safety_check.get("filtered_text", content)

        # 3. Retrieve or Create Conversation Session
        conv = (
            db.query(ChatConversation)
            .filter(
                or_(
                    and_(ChatConversation.user_a_id == sender_id, ChatConversation.user_b_id == receiver_id),
                    and_(ChatConversation.user_a_id == receiver_id, ChatConversation.user_b_id == sender_id),
                )
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        if not conv:
            conv = ChatConversation(
                user_a_id=sender_id,
                user_b_id=receiver_id,
                last_message_content=clean_content[:100],
                last_message_at=now,
                is_stranger_session=True,
            )
            db.add(conv)
            db.flush()
        else:
            conv.last_message_content = clean_content[:100]
            conv.last_message_at = now

        # 4. Create ChatMessage record
        msg = ChatMessage(
            conversation_id=conv.id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=clean_content,
            media_url=media_url,
            is_read=False,
            is_recalled=False,
        )
        db.add(msg)
        db.flush()

        # 5. Advance Intimacy Progression State Machine
        cls.calculate_intimacy_gain(
            db=db,
            conversation=conv,
            sender_id=sender_id,
            content=clean_content,
        )

        db.commit()
        db.refresh(msg)
        return msg

    @classmethod
    def calculate_intimacy_gain(
        cls,
        db: Session,
        conversation: ChatConversation,
        sender_id: str,
        content: str,
    ) -> IntimacyRecord:
        """Calculate and advance Soul intimacy XP points and unlock tiers."""
        intimacy = (
            db.query(IntimacyRecord)
            .filter(IntimacyRecord.conversation_id == conversation.id)
            .first()
        )

        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        if not intimacy:
            intimacy = IntimacyRecord(
                conversation_id=conversation.id,
                user_a_id=conversation.user_a_id,
                user_b_id=conversation.user_b_id,
                intimacy_score=0.0,
                current_level=IntimacyLevelEnum.SEED.value,
                interaction_days=1,
                word_count_today=0,
                last_interacted_date=today_str,
                unlocked_badges=["seed_sprout"],
            )
            db.add(intimacy)
            db.flush()

        # Day transition logic
        if intimacy.last_interacted_date != today_str:
            intimacy.interaction_days += 1
            intimacy.word_count_today = 0
            intimacy.last_interacted_date = today_str
            # Consecutive interaction daily bonus
            intimacy.intimacy_score += 5.0

        # Word count progression (capped at 500 characters per day to prevent spamming)
        daily_cap = 500
        available_cap = max(0, daily_cap - intimacy.word_count_today)
        counted_chars = min(len(content), available_cap)
        intimacy.word_count_today += len(content)

        # 10 characters = 1 XP point
        xp_gain = round(counted_chars * 0.1, 2)
        intimacy.intimacy_score += xp_gain

        # Evaluate level and badge progression
        badges = set(intimacy.unlocked_badges or [])
        score = intimacy.intimacy_score

        for threshold, level_name, badge_key in cls.INTIMACY_THRESHOLDS:
            if score >= threshold:
                intimacy.current_level = level_name
                badges.add(badge_key)
                break

        intimacy.unlocked_badges = list(badges)
        return intimacy

    @classmethod
    def recall_message(
        cls,
        db: Session,
        message_id: str,
        user_id: str,
    ) -> ChatMessage:
        """Recall a sent message within strict 2-minute time window."""
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        if msg.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only recall messages sent by yourself",
            )

        if msg.is_recalled:
            return msg

        now = datetime.now(timezone.utc)
        msg_time = msg.created_at
        if msg_time.tzinfo is None:
            msg_time = msg_time.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now - msg_time).total_seconds()
        if elapsed_seconds > 120.0:  # 2 minutes
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="消息发送已超过 2 分钟，无法撤回",
            )

        msg.is_recalled = True
        msg.recalled_at = now
        msg.content = "该消息已被撤回"
        db.commit()
        db.refresh(msg)
        return msg

    @classmethod
    def get_conversation_history(
        cls,
        db: Session,
        conversation_id: str,
        current_user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatMessage]:
        """Fetch conversation messages and automatically clear unread receipts."""
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Clear unread flags for received messages
        if current_user_id:
            for m in messages:
                if m.receiver_id == current_user_id and not m.is_read:
                    m.is_read = True
            db.commit()

        return messages


# Module-level convenience functions matching architecture symbols
generate_icebreakers = ChatService.generate_icebreakers
record_message = ChatService.record_message
calculate_intimacy_gain = ChatService.calculate_intimacy_gain
recall_message = ChatService.recall_message
get_conversation_history = ChatService.get_conversation_history
