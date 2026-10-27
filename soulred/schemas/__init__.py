"""Pydantic schemas package for SoulRed platform.

Exports request and response models across all functional domains.
"""

from soulred.schemas.user import (
    UserCreate,
    UserLogin,
    TokenResponse,
    UserProfileUpdate,
    UserProfileResponse,
    PrivacySettingSchema,
    VerificationBadgeResponse,
    VerificationSubmitSchema,
)
from soulred.schemas.post import (
    PostImageSchema,
    PostCreate,
    PostWaterfallCard,
    PostAuthorInfo,
    PostDetailResponse,
    PostDraftSave,
    PostLikeToggleResponse,
)
from soulred.schemas.match import (
    QuizSubmitSchema,
    QuizResultResponse,
    SoulRadarMatchCard,
    DailyCardResponse,
    CrushActionRequest,
    CrushActionResponse,
)
from soulred.schemas.chat import (
    MessageSendSchema,
    MessageResponse,
    ConversationSummaryResponse,
    IcebreakerResponse,
    IntimacyStatusResponse,
    MessageRecallRequest,
)
from soulred.schemas.circle import (
    CircleCreateSchema,
    CircleResponse,
    CommentCreateSchema,
    CommentResponse,
    CommentTreeResponse,
    ModerationActionSchema,
)

__all__ = [
    # User / Auth
    "UserCreate",
    "UserLogin",
    "TokenResponse",
    "UserProfileUpdate",
    "UserProfileResponse",
    "PrivacySettingSchema",
    "VerificationBadgeResponse",
    "VerificationSubmitSchema",
    # Post / Waterfall
    "PostImageSchema",
    "PostCreate",
    "PostWaterfallCard",
    "PostAuthorInfo",
    "PostDetailResponse",
    "PostDraftSave",
    "PostLikeToggleResponse",
    # Match / Soul / QingTeng
    "QuizSubmitSchema",
    "QuizResultResponse",
    "SoulRadarMatchCard",
    "DailyCardResponse",
    "CrushActionRequest",
    "CrushActionResponse",
    # Chat / Real-time IM
    "MessageSendSchema",
    "MessageResponse",
    "ConversationSummaryResponse",
    "IcebreakerResponse",
    "IntimacyStatusResponse",
    "MessageRecallRequest",
    # Circle / Comments / Moderation
    "CircleCreateSchema",
    "CircleResponse",
    "CommentCreateSchema",
    "CommentResponse",
    "CommentTreeResponse",
    "ModerationActionSchema",
]
