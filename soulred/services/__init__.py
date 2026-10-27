"""Core domain services and business logic algorithms for SoulRed platform.

Exports:
- AuthService: User registration, credential authentication, verification badges, privacy masking
- ContentSafetyService: AI multimodal & sensitive keyword risk interception
- PostService: Xiaohongshu-style rich note publishing, auto-drafts, and like counters
- FeedService: Dual-column waterfall feed layout computation & dynamic channel ranking
- MatchingService: Soul vector cosine similarity, radar discovery, QingTeng daily cards, and crush state machine
- ChatService: Real-time messaging, AI smart icebreakers, intimacy progression, and 2-min message recall
- CircleService: Thematic interest circles, multi-tier comment trees, and content moderation
"""

from soulred.services.auth_service import AuthService
from soulred.services.safety_service import ContentSafetyService
from soulred.services.post_service import PostService
from soulred.services.feed_service import FeedService
from soulred.services.matching_service import MatchingService
from soulred.services.chat_service import ChatService
from soulred.services.circle_service import CircleService

__all__ = [
    "AuthService",
    "ContentSafetyService",
    "PostService",
    "FeedService",
    "MatchingService",
    "ChatService",
    "CircleService",
]
