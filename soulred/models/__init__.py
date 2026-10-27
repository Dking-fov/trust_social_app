"""ORM Models package registration for SoulRed platform.

Exports all SQLAlchemy declarative models and domain enums.
"""

from soulred.database import Base
from soulred.models.base import TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin
from soulred.models.user import (
    User,
    UserProfile,
    VerificationBadge,
    PrivacySetting,
    VerificationStatusEnum,
    VerificationTypeEnum,
    GenderEnum,
)
from soulred.models.post import (
    Post,
    PostImage,
    PostLike,
    PostDraft,
    AspectRatioEnum,
    PostStatusEnum,
    MoodTagEnum,
)
from soulred.models.match import (
    PersonalityQuizResult,
    DailyRecommendation,
    CrushMatch,
    CrushStatusEnum,
)
from soulred.models.chat import (
    ChatConversation,
    ChatMessage,
    IntimacyRecord,
    MessageTypeEnum,
    IntimacyLevelEnum,
)
from soulred.models.circle import (
    InterestCircle,
    CircleMember,
    CircleComment,
    CircleRoleEnum,
    CircleCategoryEnum,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "SoftDeleteMixin",
    "User",
    "UserProfile",
    "VerificationBadge",
    "PrivacySetting",
    "VerificationStatusEnum",
    "VerificationTypeEnum",
    "GenderEnum",
    "Post",
    "PostImage",
    "PostLike",
    "PostDraft",
    "AspectRatioEnum",
    "PostStatusEnum",
    "MoodTagEnum",
    "PersonalityQuizResult",
    "DailyRecommendation",
    "CrushMatch",
    "CrushStatusEnum",
    "ChatConversation",
    "ChatMessage",
    "IntimacyRecord",
    "MessageTypeEnum",
    "IntimacyLevelEnum",
    "InterestCircle",
    "CircleMember",
    "CircleComment",
    "CircleRoleEnum",
    "CircleCategoryEnum",
]
