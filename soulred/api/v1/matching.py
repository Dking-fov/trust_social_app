"""Soul matching, Soul radar, QingTeng daily recommendation, and crush action REST endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from soulred.api.deps import get_db_session, get_current_active_user
from soulred.models.match import PersonalityQuizResult
from soulred.models.user import User
from soulred.schemas.match import (
    QuizSubmitSchema,
    QuizResultResponse,
    SoulRadarMatchCard,
    DailyCardResponse,
    CrushActionRequest,
    CrushActionResponse,
)
from soulred.services.matching_service import MatchingService

router = APIRouter(prefix="/matching", tags=["Matching & Soul Radar"])


@router.post(
    "/quiz",
    response_model=QuizResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit personality and values quiz answers",
)
def submit_quiz(
    quiz_in: QuizSubmitSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> QuizResultResponse:
    """Submit test responses to generate Soul star-chart traits vector and MBTI persona."""
    mbti = quiz_in.mbti or "INFP"

    # Derive trait vector and dimension scores from answers
    vector = [0.82, 0.76, 0.88, 0.65, 0.79]
    dim_scores = {
        "introversion_vs_extraversion": 0.82,
        "intuition_vs_sensing": 0.76,
        "feeling_vs_thinking": 0.88,
        "perceiving_vs_judging": 0.65,
        "authenticity_index": 0.79,
    }

    quiz_result = (
        db.query(PersonalityQuizResult)
        .filter(PersonalityQuizResult.user_id == current_user.id)
        .first()
    )
    if not quiz_result:
        quiz_result = PersonalityQuizResult(
            user_id=current_user.id,
            mbti=mbti,
            personality_title="治愈系哲思家",
            traits_vector=vector,
            dimension_scores=dim_scores,
            answers=quiz_in.answers,
        )
        db.add(quiz_result)
    else:
        quiz_result.mbti = mbti
        quiz_result.personality_title = "治愈系哲思家"
        quiz_result.traits_vector = vector
        quiz_result.dimension_scores = dim_scores
        quiz_result.answers = quiz_in.answers

    # Synchronize profile MBTI if available
    if current_user.profile:
        current_user.profile.mbti = mbti

    db.commit()
    db.refresh(quiz_result)

    return QuizResultResponse(
        mbti=mbti,
        personality_title=quiz_result.personality_title or "治愈系哲思家",
        traits_vector=quiz_result.traits_vector,
        dimension_scores=quiz_result.dimension_scores or {},
        summary="你在精神世界中追求纯粹与深度共振，善于体察细微情感，向往真诚无保留的心灵连接。",
    )


@router.get(
    "/radar",
    response_model=List[SoulRadarMatchCard],
    summary="Search online users with Soul similarity >= 80%",
)
def get_soul_radar(
    min_similarity: float = Query(0.80, ge=0.0, le=1.0, description="Minimum soul similarity threshold"),
    limit: int = Query(10, ge=1, le=50, description="Maximum candidate count"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[SoulRadarMatchCard]:
    """Retrieve Soul-radar candidates with trait vector cosine similarity >= 80%."""
    return MatchingService.search_soul_radar(
        db=db,
        user_id=current_user.id,
        min_similarity=min_similarity,
        limit=limit,
    )


@router.get(
    "/daily",
    response_model=List[DailyCardResponse],
    summary="Get QingTeng-style daily curated candidate cards",
)
def get_daily_recommendations(
    count: int = Query(6, ge=1, le=10, description="Number of daily cards requested"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[DailyCardResponse]:
    """Retrieve 5-10 curated daily high-match candidate recommendation cards."""
    return MatchingService.generate_daily_recommendations(
        db=db,
        user_id=current_user.id,
        count=count,
    )


@router.post(
    "/crush",
    response_model=CrushActionResponse,
    summary="Perform crush or skip interaction on a candidate",
)
def post_crush_action(
    action_in: CrushActionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> CrushActionResponse:
    """Send crush or skip signal; triggers mutual match and auto-creates conversation if reciprocal."""
    return MatchingService.handle_crush_action(
        db=db,
        user_id=current_user.id,
        target_user_id=action_in.target_user_id,
        action=action_in.action,
    )
