"""Daily 10-candidate pool generation, multi-factor ranking, mutual like logic, and targeted search."""

from datetime import date, datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User, VerificationStatusEnum, DatingPreferenceEnum, GenderEnum
from src.models.matching import (
    CandidateDeck,
    SwipeAction,
    Match,
    SwipeTypeEnum,
    MatchStatusEnum,
)
from src.models.chat import Conversation, ConversationStatusEnum, ChatMessage, MessageTypeEnum
from src.models.points import PointReasonEnum
from src.schemas.matching_schemas import (
    CandidateCardDTO,
    DailyDeckResponse,
    SwipeResultResponse,
    TargetedSearchRequest,
    CrushApplicationRequest,
    CrushApplicationResponse,
)
from src.core.exceptions import AppBaseException, AppErrorCode
from src.services.websocket_manager import ws_manager
from src.services.points_service import PointsService

settings = get_settings()


class MatchingService:
    """Core recommendation ranking engine and mutual matching service."""

    @classmethod
    def calculate_exposure_score(cls, candidate: User, current_time: Optional[datetime] = None) -> float:
        """Computes exposure ranking score:
        Score = 0.70 * BayesianReputationScore + 0.20 * ColdStartBonus + 0.10 * RecencyBonus.
        - ColdStartBonus: 1.0 if within 72h of verification, else 0.0.
        - RecencyBonus: 1.0 if active within 48h, else 0.0.
        """
        now = current_time or datetime.utcnow()

        # Cold-start bonus (72 hours)
        cold_start = 0.0
        if candidate.verified_at:
            if (now - candidate.verified_at) <= timedelta(hours=72):
                cold_start = 1.0

        # Recency bonus (48 hours)
        recency = 0.0
        if candidate.last_active_at:
            if (now - candidate.last_active_at) <= timedelta(hours=48):
                recency = 1.0

        # Multi-factor score
        score = (
            0.70 * float(candidate.reputation_score)
            + 0.20 * cold_start
            + 0.10 * recency
        )
        return round(score, 4)

    @classmethod
    async def get_or_create_daily_deck(
        cls,
        db: AsyncSession,
        user: User,
    ) -> DailyDeckResponse:
        """Retrieves or builds the daily curated 10-candidate quota card deck."""
        today = date.today()

        stmt = select(CandidateDeck).where(
            and_(CandidateDeck.user_id == user.id, CandidateDeck.deck_date == today)
        )
        deck = (await db.execute(stmt)).scalar_one_or_none()

        if not deck:
            # Generate candidate pool
            # Find users already swiped by this user
            swiped_stmt = select(SwipeAction.target_user_id).where(SwipeAction.user_id == user.id)
            swiped_ids = (await db.execute(swiped_stmt)).scalars().all()

            # Filter candidates by verification status and dating preferences
            query = select(User).where(
                and_(
                    User.id != user.id,
                    User.verification_status == VerificationStatusEnum.VERIFIED,
                    User.is_active.is_(True),
                    ~User.id.in_(list(swiped_ids) or [-1]),
                )
            )

            # Preference filters
            if user.dating_preference == DatingPreferenceEnum.MALE:
                query = query.where(User.gender == GenderEnum.MALE)
            elif user.dating_preference == DatingPreferenceEnum.FEMALE:
                query = query.where(User.gender == GenderEnum.FEMALE)

            # Target user dating preference should match current user gender
            if user.gender == GenderEnum.MALE:
                query = query.where(
                    or_(
                        User.dating_preference == DatingPreferenceEnum.MALE,
                        User.dating_preference == DatingPreferenceEnum.BOTH,
                    )
                )
            elif user.gender == GenderEnum.FEMALE:
                query = query.where(
                    or_(
                        User.dating_preference == DatingPreferenceEnum.FEMALE,
                        User.dating_preference == DatingPreferenceEnum.BOTH,
                    )
                )

            all_candidates = (await db.execute(query)).scalars().all()

            # Rank by multi-factor exposure score
            scored_candidates = [
                (c, cls.calculate_exposure_score(c)) for c in all_candidates
            ]
            scored_candidates.sort(key=lambda x: x[1], reverse=True)

            # Pick top 10 quota
            top_candidates = scored_candidates[: settings.DAILY_RECOMMENDATION_QUOTA]
            candidate_ids = [c.id for c, _ in top_candidates]

            deck = CandidateDeck(
                user_id=user.id,
                deck_date=today,
                candidate_ids=candidate_ids,
                remaining_cards=len(candidate_ids),
                refreshed_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(deck)
            await db.commit()
            await db.refresh(deck)

        # Calculate seconds until midnight reset
        tomorrow = today + timedelta(days=1)
        reset_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        seconds_until_reset = max(0, int((reset_time - datetime.utcnow()).total_seconds()))

        # Load candidates currently remaining in deck
        remaining_candidates_dto: List[CandidateCardDTO] = []
        if deck.remaining_cards > 0 and deck.candidate_ids:
            # Look up candidate entities
            cand_stmt = select(User).where(User.id.in_(deck.candidate_ids))
            cand_res = (await db.execute(cand_stmt)).scalars().all()
            cand_map = {c.id: c for c in cand_res}

            for cid in deck.candidate_ids[: deck.remaining_cards]:
                if cid in cand_map:
                    c = cand_map[cid]
                    score = cls.calculate_exposure_score(c)
                    school_tier = None
                    degree_level = None
                    if c.education_credential:
                        school_tier = c.education_credential.school_tier
                        degree_level = c.education_credential.degree_level

                    dto = CandidateCardDTO(
                        id=c.id,
                        nickname=c.nickname,
                        age=c.age,
                        resident_city=c.resident_city,
                        gender=c.gender,
                        interest_tags=c.interest_tags,
                        reputation_score=c.reputation_score,
                        reputation_count=c.reputation_count,
                        school_tier=school_tier,
                        degree_level=degree_level,
                        is_verified=c.verification_status == VerificationStatusEnum.VERIFIED,
                        ranking_score=score,
                    )
                    remaining_candidates_dto.append(dto)

        return DailyDeckResponse(
            deck_date=deck.deck_date,
            remaining_cards=deck.remaining_cards,
            refreshed_count=deck.refreshed_count,
            seconds_until_reset=seconds_until_reset,
            candidates=remaining_candidates_dto,
        )

    @classmethod
    async def process_swipe(
        cls,
        db: AsyncSession,
        user: User,
        target_user_id: int,
        action: SwipeTypeEnum,
    ) -> SwipeResultResponse:
        """Processes a swipe action, consumes 1 card, checks mutual like, and creates match."""
        today = date.today()

        # Check existing swipe
        swipe_stmt = select(SwipeAction).where(
            and_(SwipeAction.user_id == user.id, SwipeAction.target_user_id == target_user_id)
        )
        existing_swipe = (await db.execute(swipe_stmt)).scalar_one_or_none()

        if not existing_swipe:
            swipe = SwipeAction(
                user_id=user.id,
                target_user_id=target_user_id,
                action=action,
                created_at=datetime.utcnow(),
            )
            db.add(swipe)

            # Decrement today's deck card count
            deck_stmt = select(CandidateDeck).where(
                and_(CandidateDeck.user_id == user.id, CandidateDeck.deck_date == today)
            )
            deck = (await db.execute(deck_stmt)).scalar_one_or_none()
            if deck and deck.remaining_cards > 0:
                deck.remaining_cards -= 1
                if target_user_id in deck.candidate_ids:
                    # Keep track of consumed candidate
                    deck.candidate_ids = [cid for cid in deck.candidate_ids if cid != target_user_id]
            remaining_cards = deck.remaining_cards if deck else 0
        else:
            deck_stmt = select(CandidateDeck).where(
                and_(CandidateDeck.user_id == user.id, CandidateDeck.deck_date == today)
            )
            deck = (await db.execute(deck_stmt)).scalar_one_or_none()
            remaining_cards = deck.remaining_cards if deck else 0

        is_match = False
        match_id = None
        conv_id = None

        if action == SwipeTypeEnum.LIKE:
            # Check if target user previously liked this user
            reciprocal_stmt = select(SwipeAction).where(
                and_(
                    SwipeAction.user_id == target_user_id,
                    SwipeAction.target_user_id == user.id,
                    SwipeAction.action == SwipeTypeEnum.LIKE,
                )
            )
            reciprocal = (await db.execute(reciprocal_stmt)).scalar_one_or_none()

            if reciprocal:
                # Double opt-in mutual match!
                is_match = True
                user_a = min(user.id, target_user_id)
                user_b = max(user.id, target_user_id)

                # Check or create Match
                match_stmt = select(Match).where(
                    and_(Match.user_a_id == user_a, Match.user_b_id == user_b)
                )
                match = (await db.execute(match_stmt)).scalar_one_or_none()
                if not match:
                    match = Match(
                        user_a_id=user_a,
                        user_b_id=user_b,
                        status=MatchStatusEnum.ACTIVE,
                        matched_at=datetime.utcnow(),
                    )
                    db.add(match)
                    await db.flush()

                match_id = match.id

                # Create 1v1 conversation
                conv_stmt = select(Conversation).where(Conversation.match_id == match.id)
                conv = (await db.execute(conv_stmt)).scalar_one_or_none()
                if not conv:
                    conv = Conversation(
                        match_id=match.id,
                        user_a_id=user_a,
                        user_b_id=user_b,
                        status=ConversationStatusEnum.ACTIVE,
                        message_count=0,
                        created_at=datetime.utcnow(),
                    )
                    db.add(conv)
                    await db.flush()

                conv_id = conv.id

                # Broadcast match success to both connected websockets
                await ws_manager.broadcast_to_match(
                    user_a_id=user_a,
                    user_b_id=user_b,
                    event="match_success",
                    data={
                        "match_id": match.id,
                        "conversation_id": conv.id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        await db.commit()

        return SwipeResultResponse(
            success=True,
            is_match=is_match,
            remaining_cards=remaining_cards,
            match_id=match_id,
            conversation_id=conv_id,
        )

    @classmethod
    async def perform_targeted_search(
        cls,
        db: AsyncSession,
        user: User,
        req: TargetedSearchRequest,
    ) -> List[CandidateCardDTO]:
        """Deducts 100 points and returns high-reputation candidates (top percentile)."""
        # Deduct 100 points
        idempotency = f"targeted_search_{user.id}_{datetime.utcnow().timestamp()}"
        await PointsService.deduct_points(
            db=db,
            user=user,
            amount=settings.TARGETED_SEARCH_COST_POINTS,
            reason=PointReasonEnum.TARGETED_SEARCH,
            idempotency_key=idempotency,
            description=f"Targeted discovery search in {req.city or 'all cities'}",
        )

        query = select(User).where(
            and_(
                User.id != user.id,
                User.verification_status == VerificationStatusEnum.VERIFIED,
                User.is_active.is_(True),
            )
        )
        if req.city:
            query = query.where(User.resident_city == req.city)

        all_candidates = (await db.execute(query)).scalars().all()
        if not all_candidates:
            return []

        # Sort by reputation score descending
        all_candidates.sort(key=lambda u: u.reputation_score, reverse=True)
        # Filter top percentile (e.g. top 10%)
        cutoff = max(1, int(len(all_candidates) * req.top_percentile))
        top_candidates = all_candidates[:cutoff]

        results = []
        for c in top_candidates:
            school_tier = c.education_credential.school_tier if c.education_credential else None
            degree_level = c.education_credential.degree_level if c.education_credential else None
            results.append(
                CandidateCardDTO(
                    id=c.id,
                    nickname=c.nickname,
                    age=c.age,
                    resident_city=c.resident_city,
                    gender=c.gender,
                    interest_tags=c.interest_tags,
                    reputation_score=c.reputation_score,
                    reputation_count=c.reputation_count,
                    school_tier=school_tier,
                    degree_level=degree_level,
                    is_verified=True,
                    ranking_score=c.reputation_score,
                )
            )

        return results

    @classmethod
    async def send_crush_application(
        cls,
        db: AsyncSession,
        user: User,
        req: CrushApplicationRequest,
    ) -> CrushApplicationResponse:
        """Sends direct crush application bypassing standard card deck limits."""
        # Target user must exist and be verified
        target_stmt = select(User).where(User.id == req.target_user_id)
        target = (await db.execute(target_stmt)).scalar_one_or_none()
        if not target:
            raise AppBaseException(
                status_code=404,
                error_code=AppErrorCode.ERR_NOT_FOUND,
                message="Target candidate not found.",
            )

        # Record a like from user to target
        swipe_stmt = select(SwipeAction).where(
            and_(SwipeAction.user_id == user.id, SwipeAction.target_user_id == target.id)
        )
        swipe = (await db.execute(swipe_stmt)).scalar_one_or_none()
        if not swipe:
            swipe = SwipeAction(
                user_id=user.id,
                target_user_id=target.id,
                action=SwipeTypeEnum.LIKE,
                created_at=datetime.utcnow(),
            )
            db.add(swipe)
            await db.commit()

        # Send real-time notification to target priority inbox
        await ws_manager.send_personal_message(
            message={
                "event": "priority_crush_application",
                "data": {
                    "sender_id": user.id,
                    "sender_nickname": user.nickname,
                    "intro_note": req.intro_note,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            user_id=target.id,
        )

        return CrushApplicationResponse(
            success=True,
            target_user_id=target.id,
            message="Crush application delivered to recipient priority inbox.",
        )
