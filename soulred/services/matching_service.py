"""Soul & QingTeng matching engine, radar search, daily cards, and crush state machine.

Implements:
- Multidimensional personality & values vector cosine similarity algorithm
- Soul Radar candidate filtering (similarity >= 80%)
- QingTeng-style curated daily recommendation cards (5-10 cards)
- Bidirectional crush state machine (CrushStatusEnum.MUTUAL triggers automatic chat channel creation)
- Stranger anti-harassment quota control (single daily greeting text, zero images/voice)
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from soulred.config import get_settings
from soulred.models.match import (
    PersonalityQuizResult,
    DailyRecommendation,
    CrushMatch,
    CrushStatusEnum,
)
from soulred.models.user import User, UserProfile
from soulred.models.chat import (
    ChatConversation,
    ChatMessage,
    IntimacyRecord,
    IntimacyLevelEnum,
    MessageTypeEnum,
)
from soulred.schemas.match import (
    SoulRadarMatchCard,
    DailyCardResponse,
    CrushActionResponse,
)


class MatchingService:
    """Core domain service for interest matching, radar, and crush state transitions."""

    # Pre-defined complementary MBTI golden pairs
    MBTI_GOLDEN_PAIRS = {
        ("INFP", "ENFJ"), ("ENFJ", "INFP"),
        ("INTJ", "ENFP"), ("ENFP", "INTJ"),
        ("INFJ", "ENTP"), ("ENTP", "INFJ"),
        ("INTP", "ENTJ"), ("ENTJ", "INTP"),
        ("ISFP", "ESFJ"), ("ESFJ", "ISFP"),
        ("ISTJ", "ESTP"), ("ESTP", "ISTJ"),
        ("ISFJ", "ESFP"), ("ESFP", "ISFJ"),
        ("ISTP", "ESTJ"), ("ESTJ", "ISTP"),
    }

    @classmethod
    def calculate_soul_similarity(
        cls,
        vector_a: List[float],
        vector_b: List[float],
        mbti_a: Optional[str] = None,
        mbti_b: Optional[str] = None,
    ) -> float:
        """Compute multidimensional trait vector cosine similarity with MBTI synergy bonus."""
        if not vector_a or not vector_b:
            return 0.50

        # Truncate to common length
        dim = min(len(vector_a), len(vector_b))
        if dim == 0:
            return 0.50

        vec_a = vector_a[:dim]
        vec_b = vector_b[:dim]

        dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(y * y for y in vec_b))

        if norm_a == 0 or norm_b == 0:
            cosine_sim = 0.50
        else:
            cosine_sim = dot_product / (norm_a * norm_b)
            # Bound cosine between 0.0 and 1.0 (assuming non-negative trait space)
            cosine_sim = max(0.0, min(1.0, cosine_sim))

        # MBTI synergy bonus
        if mbti_a and mbti_b:
            m_a = mbti_a.strip().upper()
            m_b = mbti_b.strip().upper()
            if (m_a, m_b) in cls.MBTI_GOLDEN_PAIRS:
                cosine_sim = min(1.0, cosine_sim + 0.08)
            elif m_a == m_b:
                cosine_sim = min(1.0, cosine_sim + 0.04)

        return round(cosine_sim, 3)

    @classmethod
    def search_soul_radar(
        cls,
        db: Session,
        user_id: str,
        min_similarity: float = 0.80,
        limit: int = 10,
    ) -> List[SoulRadarMatchCard]:
        """Search active users with soul similarity >= min_similarity (default 80%)."""
        # User's own quiz result & profile
        my_quiz = (
            db.query(PersonalityQuizResult)
            .filter(PersonalityQuizResult.user_id == user_id)
            .first()
        )
        my_user = db.query(User).filter(User.id == user_id).first()
        my_profile = my_user.profile if my_user else None

        my_vector = my_quiz.traits_vector if my_quiz else [0.7, 0.8, 0.65, 0.85, 0.75]
        my_mbti = my_profile.mbti if my_profile else (my_quiz.mbti if my_quiz else None)
        my_tags = set(my_profile.interest_tags or []) if my_profile else set()

        # Candidates (exclude self)
        candidate_quizzes = (
            db.query(PersonalityQuizResult)
            .filter(PersonalityQuizResult.user_id != user_id)
            .all()
        )

        match_cards: List[SoulRadarMatchCard] = []

        for c_quiz in candidate_quizzes:
            c_user = db.query(User).filter(User.id == c_quiz.user_id).first()
            if not c_user or not c_user.is_active:
                continue

            c_profile = c_user.profile
            if not c_profile:
                continue

            # Check privacy setting
            privacy = c_user.privacy_setting
            if privacy and privacy.incognito_contacts:
                continue

            c_mbti = c_profile.mbti or c_quiz.mbti
            similarity = cls.calculate_soul_similarity(
                my_vector,
                c_quiz.traits_vector,
                mbti_a=my_mbti,
                mbti_b=c_mbti,
            )

            if similarity >= min_similarity:
                c_tags = set(c_profile.interest_tags or [])
                common_tags = list(my_tags.intersection(c_tags))

                match_cards.append(
                    SoulRadarMatchCard(
                        user_id=c_user.id,
                        nickname=c_profile.nickname,
                        avatar_url=c_profile.avatar_url,
                        mbti=c_mbti,
                        match_score=similarity,
                        common_tags=common_tags,
                        voice_card_url=c_profile.voice_card_url,
                        personality_title=c_quiz.personality_title or "灵性探索者",
                    )
                )

        # Sort by similarity score descending
        match_cards.sort(key=lambda card: card.match_score, reverse=True)
        return match_cards[:limit]

    @classmethod
    def generate_daily_recommendations(
        cls,
        db: Session,
        user_id: str,
        count: int = 6,
    ) -> List[DailyCardResponse]:
        """Generate or retrieve QingTeng-style daily curated cards for the user."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Check existing recommendations for today
        existing = (
            db.query(DailyRecommendation)
            .filter(
                DailyRecommendation.user_id == user_id,
                DailyRecommendation.date_str == today_str,
            )
            .all()
        )

        if existing:
            cards: List[DailyCardResponse] = []
            for rec in existing:
                t_user = db.query(User).filter(User.id == rec.target_user_id).first()
                if not t_user:
                    continue
                profile = t_user.profile
                cards.append(
                    DailyCardResponse(
                        card_id=rec.id,
                        target_user_id=t_user.id,
                        nickname=profile.nickname if profile else t_user.username,
                        avatar_url=profile.avatar_url if profile else None,
                        age=profile.age if profile else 24,
                        mbti=profile.mbti if profile else None,
                        job_or_school=profile.location if profile else "自由职业",
                        tags=profile.interest_tags if profile else [],
                        match_score=rec.match_score,
                        match_reasons=rec.reasons or ["生活步调一致"],
                        photo_urls=[profile.avatar_url] if profile and profile.avatar_url else [],
                        voice_card_url=profile.voice_card_url if profile else None,
                        date_str=rec.date_str,
                    )
                )
            return cards

        # 2. Generate new daily recommendations
        candidates = (
            db.query(User)
            .filter(User.id != user_id, User.is_active == True)
            .limit(count * 2)
            .all()
        )

        my_quiz = (
            db.query(PersonalityQuizResult)
            .filter(PersonalityQuizResult.user_id == user_id)
            .first()
        )
        my_vector = my_quiz.traits_vector if my_quiz else [0.7, 0.8, 0.65, 0.85, 0.75]

        created_cards: List[DailyCardResponse] = []
        for c_user in candidates[:count]:
            c_profile = c_user.profile
            c_quiz = (
                db.query(PersonalityQuizResult)
                .filter(PersonalityQuizResult.user_id == c_user.id)
                .first()
            )
            c_vector = c_quiz.traits_vector if c_quiz else [0.72, 0.79, 0.68, 0.80, 0.70]

            score = cls.calculate_soul_similarity(my_vector, c_vector)
            reasons = ["兴趣爱好高度重合", "价值观测试契合度极佳"]

            rec = DailyRecommendation(
                user_id=user_id,
                target_user_id=c_user.id,
                date_str=today_str,
                match_score=score,
                reasons=reasons,
                is_crushed=False,
                is_skipped=False,
            )
            db.add(rec)
            db.flush()

            created_cards.append(
                DailyCardResponse(
                    card_id=rec.id,
                    target_user_id=c_user.id,
                    nickname=c_profile.nickname if c_profile else c_user.username,
                    avatar_url=c_profile.avatar_url if c_profile else None,
                    age=c_profile.age if c_profile else 24,
                    mbti=c_profile.mbti if c_profile else None,
                    job_or_school=c_profile.location if c_profile else "青年独立创作者",
                    tags=c_profile.interest_tags if c_profile else ["摄影", "自驾", "独立音乐"],
                    match_score=score,
                    match_reasons=reasons,
                    photo_urls=[c_profile.avatar_url] if c_profile and c_profile.avatar_url else [],
                    voice_card_url=c_profile.voice_card_url if c_profile else None,
                    date_str=today_str,
                )
            )

        db.commit()
        return created_cards

    @classmethod
    def handle_crush_action(
        cls,
        db: Session,
        user_id: str,
        target_user_id: str,
        action: str,
    ) -> CrushActionResponse:
        """Process crush or skip action and trigger mutual match state machine."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Update daily recommendation flag if present
        rec = (
            db.query(DailyRecommendation)
            .filter(
                DailyRecommendation.user_id == user_id,
                DailyRecommendation.target_user_id == target_user_id,
                DailyRecommendation.date_str == today_str,
            )
            .first()
        )

        if action.lower() == "skip":
            if rec:
                rec.is_skipped = True

            crush = (
                db.query(CrushMatch)
                .filter(
                    CrushMatch.user_id == user_id,
                    CrushMatch.target_user_id == target_user_id,
                )
                .first()
            )
            if not crush:
                crush = CrushMatch(
                    user_id=user_id,
                    target_user_id=target_user_id,
                    status=CrushStatusEnum.SKIPPED.value,
                )
                db.add(crush)
            else:
                crush.status = CrushStatusEnum.SKIPPED.value

            db.commit()
            return CrushActionResponse(
                user_id=user_id,
                target_user_id=target_user_id,
                status=CrushStatusEnum.SKIPPED.value,
                is_mutual=False,
                message="已跳过该推荐",
            )

        # 2. Action is 'crush'
        if rec:
            rec.is_crushed = True

        # Check if the target user has already crushed on current user
        reverse_crush = (
            db.query(CrushMatch)
            .filter(
                CrushMatch.user_id == target_user_id,
                CrushMatch.target_user_id == user_id,
                CrushMatch.status.in_([CrushStatusEnum.PENDING.value, "crush"]),
            )
            .first()
        )

        now = datetime.now(timezone.utc)

        if reverse_crush:
            # MUTUAL MATCH EVENT (双向奔赴)
            reverse_crush.status = CrushStatusEnum.MUTUAL.value
            reverse_crush.mutual_at = now

            my_crush = (
                db.query(CrushMatch)
                .filter(
                    CrushMatch.user_id == user_id,
                    CrushMatch.target_user_id == target_user_id,
                )
                .first()
            )
            if not my_crush:
                my_crush = CrushMatch(
                    user_id=user_id,
                    target_user_id=target_user_id,
                    status=CrushStatusEnum.MUTUAL.value,
                    mutual_at=now,
                )
                db.add(my_crush)
            else:
                my_crush.status = CrushStatusEnum.MUTUAL.value
                my_crush.mutual_at = now

            # Automatically establish dedicated private chat conversation channel
            conv = (
                db.query(ChatConversation)
                .filter(
                    or_(
                        and_(ChatConversation.user_a_id == user_id, ChatConversation.user_b_id == target_user_id),
                        and_(ChatConversation.user_a_id == target_user_id, ChatConversation.user_b_id == user_id),
                    )
                )
                .first()
            )

            if not conv:
                conv = ChatConversation(
                    user_a_id=user_id,
                    user_b_id=target_user_id,
                    last_message_content="【系统消息】恭喜双方互相心动，双向奔赴成功！快来打个招呼吧～",
                    last_message_at=now,
                    is_stranger_session=False,
                )
                db.add(conv)
                db.flush()

                # Initialize Intimacy Record
                intimacy = IntimacyRecord(
                    conversation_id=conv.id,
                    user_a_id=user_id,
                    user_b_id=target_user_id,
                    intimacy_score=10.0,
                    current_level=IntimacyLevelEnum.SEED.value,
                    interaction_days=1,
                    unlocked_badges=["mutual_crush"],
                )
                db.add(intimacy)
            else:
                conv.is_stranger_session = False

            my_crush.conversation_id = conv.id
            reverse_crush.conversation_id = conv.id

            db.commit()
            return CrushActionResponse(
                user_id=user_id,
                target_user_id=target_user_id,
                status=CrushStatusEnum.MUTUAL.value,
                is_mutual=True,
                conversation_id=conv.id,
                message="双向奔赴成功！已为你自动建立专属私聊通道，快去破冰吧！",
            )

        # Single-sided crush
        my_crush = (
            db.query(CrushMatch)
            .filter(
                CrushMatch.user_id == user_id,
                CrushMatch.target_user_id == target_user_id,
            )
            .first()
        )
        if not my_crush:
            my_crush = CrushMatch(
                user_id=user_id,
                target_user_id=target_user_id,
                status=CrushStatusEnum.PENDING.value,
            )
            db.add(my_crush)
        else:
            my_crush.status = CrushStatusEnum.PENDING.value

        db.commit()
        return CrushActionResponse(
            user_id=user_id,
            target_user_id=target_user_id,
            status=CrushStatusEnum.PENDING.value,
            is_mutual=False,
            message="心动信号已发送，等待对方回应～",
        )

    @classmethod
    def check_stranger_message_limit(
        cls,
        db: Session,
        sender_id: str,
        receiver_id: str,
        message_type: str = "text",
    ) -> bool:
        """Verify whether sender can message receiver under stranger anti-harassment rules.

        Rules:
        - Mutual friends / crushed users have NO quota or media restrictions.
        - Strangers are restricted to:
            1. ONLY 'text' message type (NO image, NO voice).
            2. At most 1 message per calendar day.
        """
        # 1. Check mutual crush or established non-stranger session
        mutual = (
            db.query(CrushMatch)
            .filter(
                or_(
                    and_(CrushMatch.user_id == sender_id, CrushMatch.target_user_id == receiver_id),
                    and_(CrushMatch.user_id == receiver_id, CrushMatch.target_user_id == sender_id),
                ),
                CrushMatch.status == CrushStatusEnum.MUTUAL.value,
            )
            .first()
        )
        if mutual:
            return True

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
        if conv and not conv.is_stranger_session:
            return True

        # 2. Stranger constraints
        if message_type.lower() != MessageTypeEnum.TEXT.value:
            # Strangers cannot send non-text messages
            return False

        # 3. Check daily count
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        sent_count = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.sender_id == sender_id,
                ChatMessage.receiver_id == receiver_id,
                ChatMessage.created_at >= today_start,
            )
            .count()
        )

        settings = get_settings()
        limit = getattr(settings, "STRANGER_DAILY_MSG_LIMIT", 1)
        return sent_count < limit


# Module-level convenience functions matching architecture symbols
calculate_soul_similarity = MatchingService.calculate_soul_similarity
search_soul_radar = MatchingService.search_soul_radar
generate_daily_recommendations = MatchingService.generate_daily_recommendations
handle_crush_action = MatchingService.handle_crush_action
check_stranger_message_limit = MatchingService.check_stranger_message_limit
