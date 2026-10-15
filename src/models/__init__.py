"""Aggregates and exports all database entities for clean imports and SQLAlchemy metadata binding."""

from src.models.user import (
    User,
    EducationCredential,
    GenderEnum,
    DatingPreferenceEnum,
    VerificationStatusEnum,
    SchoolTierEnum,
    DegreeLevelEnum,
)
from src.models.matching import (
    CandidateDeck,
    SwipeAction,
    Match,
    SwipeTypeEnum,
    MatchStatusEnum,
)
from src.models.chat import (
    Conversation,
    ChatMessage,
    ConversationStatusEnum,
    MessageTypeEnum,
)
from src.models.dating import (
    DateInvitation,
    DateCheckIn,
    DateReview,
    DateStatusEnum,
    CheckInMethodEnum,
    ReviewStatusEnum,
)
from src.models.points import (
    PointLedger,
    DailyActivityLog,
    PointReasonEnum,
)

__all__ = [
    "User",
    "EducationCredential",
    "GenderEnum",
    "DatingPreferenceEnum",
    "VerificationStatusEnum",
    "SchoolTierEnum",
    "DegreeLevelEnum",
    "CandidateDeck",
    "SwipeAction",
    "Match",
    "SwipeTypeEnum",
    "MatchStatusEnum",
    "Conversation",
    "ChatMessage",
    "ConversationStatusEnum",
    "MessageTypeEnum",
    "DateInvitation",
    "DateCheckIn",
    "DateReview",
    "DateStatusEnum",
    "CheckInMethodEnum",
    "ReviewStatusEnum",
    "PointLedger",
    "DailyActivityLog",
    "PointReasonEnum",
]
