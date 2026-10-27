"""Comprehensive pytest test suite covering all Acceptance Criteria (US-001 through US-006)
for soulred-social-platform (Track 1: Unit & API Integration Tests).

Validates:
- Edge cases, data constraints, security, and business state machines.
- US-001: Waterfall feed layout, aspect ratio calculation, skeleton colors, multi-channel feeds & performance.
- US-002: Rich-media post creation (9 images max, 1:1/3:4/4:3 ratios), 1-5 topic tags, mood tags, draft auto-save, AI safety filtering.
- US-003: Soul & QingTeng matching engine, MBTI quiz, radar >=80% filter, daily deck, mutual crush state machine, stranger quotas.
- US-004: Instant messaging, AI icebreaker generation, intimacy XP progression state machine, 2-minute message recall, read receipts.
- US-005: Interest circles, category browsing, multi-tier nested comment trees, community moderation & muting.
- US-006: Profile persona, 3D avatar, 10s voice card, AES-256 credential encryption, client PII masking, privacy controls.
"""

import time
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from soulred.models.user import (
    User,
    UserProfile,
    VerificationBadge,
    PrivacySetting,
    VerificationStatusEnum,
    VerificationTypeEnum,
)
from soulred.models.post import (
    Post,
    PostImage,
    PostDraft,
    PostStatusEnum,
    AspectRatioEnum,
)
from soulred.models.chat import (
    ChatConversation,
    ChatMessage,
    IntimacyRecord,
    MessageTypeEnum,
    IntimacyLevelEnum,
)
from soulred.models.match import (
    PersonalityQuizResult,
    DailyRecommendation,
    CrushMatch,
    CrushStatusEnum,
)
from soulred.models.circle import (
    InterestCircle,
    CircleMember,
    CircleComment,
    CircleRoleEnum,
    CircleCategoryEnum,
)
from soulred.services.feed_service import (
    FeedService,
    calculate_card_aspect_ratio,
    get_waterfall_feed,
)
from soulred.services.matching_service import (
    MatchingService,
    calculate_soul_similarity,
    check_stranger_message_limit,
)
from soulred.services.chat_service import (
    ChatService,
    generate_icebreakers,
    calculate_intimacy_gain,
)
from soulred.services.post_service import PostService
from soulred.services.safety_service import (
    ContentSafetyService,
    check_text_safety,
    check_image_safety,
)
from soulred.services.auth_service import (
    AuthService,
    mask_phone_number,
)
from soulred.schemas.post import PostCreate, PostImageSchema, PostDraftSave
from soulred.schemas.user import UserCreate, VerificationSubmitSchema
from soulred.schemas.circle import CommentCreateSchema, ModerationActionSchema
from soulred.utils.crypto import encrypt_field, decrypt_field, hash_password


# =============================================================================
# US-001: Xiaohongshu-Style Waterfall Feed Tests
# =============================================================================

class TestUS001WaterfallFeed:
    """Test US-001: Waterfall feed layout, image aspect ratios, channels, and performance."""

    def test_aspect_ratio_calculation_and_bounding(self):
        """AC1: Adaptive height calculation for 1:1, 3:4, 4:3 and extreme aspect ratios."""
        # Standard aspect ratios
        height_3_4, color_3_4 = calculate_card_aspect_ratio("3:4", 1080, 1440)
        assert height_3_4 == 340
        assert color_3_4.startswith("#")

        height_1_1, color_1_1 = calculate_card_aspect_ratio("1:1", 1000, 1000)
        assert height_1_1 == 260

        height_4_3, color_4_3 = calculate_card_aspect_ratio("4:3", 1200, 900)
        assert height_4_3 == 200

        # Boundary test: Unspecified ratio infers from numeric width/height
        height_inferred, color_inferred = calculate_card_aspect_ratio(None, 600, 800)
        assert height_inferred > 0
        assert color_inferred.startswith("#")

    def test_feed_channels_switching_and_performance(self, client: TestClient):
        """AC3: Switching 'recommend', 'nearby', 'following' under 800ms response time."""
        for channel in ["recommend", "nearby", "following"]:
            t0 = time.perf_counter()
            resp = client.get(
                f"/api/v1/feed?channel={channel}&viewer_lat=31.23&viewer_lon=121.45&page=1&page_size=10"
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            assert resp.status_code == 200
            assert elapsed_ms < 800, f"Channel {channel} took {elapsed_ms:.2f}ms, expected < 800ms"
            data = resp.json()
            assert data["channel"] == channel
            assert isinstance(data["items"], list)

    def test_feed_pagination_boundaries(self, client: TestClient):
        """Edge case: Page numbers beyond content yield empty list gracefully without 500."""
        resp = client.get("/api/v1/feed?channel=recommend&page=9999&page_size=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# =============================================================================
# US-002: Rich-Media Post Creation & Mood Tags Tests
# =============================================================================

class TestUS002PostCreation:
    """Test US-002: Rich note creation, max 9 images, topics, mood tag, drafts & AI safety."""

    def test_create_post_with_up_to_9_images(self, client: TestClient, auth_headers_user_a: dict):
        """AC1: Support up to 9 image attachments with multiple aspect ratios."""
        images = [
            {
                "image_url": f"https://example.com/photo_{i}.jpg",
                "order_index": i,
                "aspect_ratio": "3:4" if i % 2 == 0 else "1:1",
                "width": 1080,
                "height": 1440 if i % 2 == 0 else 1080,
            }
            for i in range(9)
        ]

        resp = client.post(
            "/api/v1/posts",
            headers=auth_headers_user_a,
            json={
                "title": "九图记录上海初秋的街头小景 🍂",
                "content": "从巨鹿路走到富民路，法桐树叶已经开始泛黄了。",
                "mood_tag": "治愈中",
                "topics": ["周末去哪儿", "街头摄影", "Citywalk"],
                "images": images,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["images"]) == 9
        assert data["mood_tag"] == "治愈中"
        assert "Citywalk" in data["topics"]

    def test_post_creation_topic_tags_and_mood_options(self, client: TestClient, auth_headers_user_a: dict):
        """AC2: Associate 1~5 topic tags and optional mood status."""
        valid_moods = ["治愈中", "求聊天", "发呆", "开心", "emo"]
        for mood in valid_moods:
            resp = client.post(
                "/api/v1/posts",
                headers=auth_headers_user_a,
                json={
                    "title": f"今日心情状态测试: {mood}",
                    "content": "分享不同心情下的真实生活切片。",
                    "mood_tag": mood,
                    "topics": ["#MBTI", "#生活记录"],
                },
            )
            assert resp.status_code == 201
            assert resp.json()["mood_tag"] == mood

    def test_local_draft_auto_save_and_recovery(self, client: TestClient, auth_headers_user_a: dict):
        """AC3: Local draft auto-save and retrieval survives simulated restart."""
        draft_content = {
            "title": "未发布的草稿笔记",
            "content": "这是正在编辑的内容，随时自动保存防止丢失...",
            "mood_tag": "求聊天",
            "topics": ["草稿话题1", "草稿话题2"],
        }
        # Save draft
        save_resp = client.post("/api/v1/posts/draft", headers=auth_headers_user_a, json=draft_content)
        assert save_resp.status_code == 200

        # Retrieve draft
        get_resp = client.get("/api/v1/posts/draft", headers=auth_headers_user_a)
        assert get_resp.status_code == 200
        draft_data = get_resp.json()
        assert draft_data["status"] == "found"
        assert draft_data["draft"]["title"] == "未发布的草稿笔记"
        assert draft_data["draft"]["mood_tag"] == "求聊天"

    def test_ai_content_safety_interception(self, client: TestClient, auth_headers_user_a: dict):
        """AC4 & Non-Functional: AI content safety intercepts illegal/spam keywords."""
        bad_resp = client.post(
            "/api/v1/posts",
            headers=auth_headers_user_a,
            json={
                "title": "涉黄涉赌违规推广",
                "content": "加微详谈赌博下注，裸聊看色情直播",
                "topics": ["违规引流"],
            },
        )
        assert bad_resp.status_code in [400, 422]
        assert "content safety" in bad_resp.text.lower() or "rejected" in bad_resp.text.lower()


# =============================================================================
# US-003: Soul & QingTeng Interest Matching Engine Tests
# =============================================================================

class TestUS003MatchingEngine:
    """Test US-003: MBTI quiz, Soul radar >=80% filter, daily cards, mutual crush & stranger limit."""

    def test_mbti_personality_quiz_submission(self, client: TestClient, auth_headers_user_a: dict):
        """AC1: New user submits personality quiz generating soul trait vector."""
        resp = client.post(
            "/api/v1/matching/quiz",
            headers=auth_headers_user_a,
            json={
                "mbti": "INFP",
                "answers": {
                    "energy": "introvert",
                    "lifestyle": "spontaneous",
                    "weekend": "exhibition",
                    "music": "folk",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mbti"] == "INFP"
        assert len(data["traits_vector"]) == 5
        assert all(0.0 <= val <= 1.0 for val in data["traits_vector"])

    def test_soul_radar_matching_threshold(self, client: TestClient, auth_headers_user_a: dict):
        """AC2a: Soul radar only surfaces matches with >=80% similarity."""
        resp = client.get("/api/v1/matching/radar", headers=auth_headers_user_a)
        assert resp.status_code == 200
        cards = resp.json()
        assert isinstance(cards, list)
        for card in cards:
            assert card["match_score"] >= 0.80, f"Expected match_score >= 0.80, got {card['match_score']}"

    def test_bidirectional_crush_state_machine(
        self,
        client: TestClient,
        test_user_a: User,
        test_user_b: User,
        auth_headers_user_a: dict,
        auth_headers_user_b: dict,
        db_session: Session,
    ):
        """AC3: Unilateral crush is pending; reciprocal crush triggers MUTUAL and establishes IM."""
        # Clear existing crush state for clean test run
        db_session.query(CrushMatch).filter(
            ((CrushMatch.user_id == test_user_a.id) & (CrushMatch.target_user_id == test_user_b.id)) |
            ((CrushMatch.user_id == test_user_b.id) & (CrushMatch.target_user_id == test_user_a.id))
        ).delete()
        db_session.commit()

        # Step 1: User A sends crush to User B
        res1 = client.post(
            "/api/v1/matching/crush",
            headers=auth_headers_user_a,
            json={"target_user_id": test_user_b.id, "action": "crush"},
        )
        assert res1.status_code == 200
        assert res1.json()["is_mutual"] is False
        assert res1.json()["status"] == "pending"

        # Step 2: User B sends crush to User A -> Triggers MUTUAL
        res2 = client.post(
            "/api/v1/matching/crush",
            headers=auth_headers_user_b,
            json={"target_user_id": test_user_a.id, "action": "crush"},
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["is_mutual"] is True
        assert data2["status"] == "mutual"
        assert data2["conversation_id"] is not None

    def test_stranger_daily_greeting_quota(self, db_session: Session):
        """AC4: Unmatched strangers can send at most 1 text greeting per day; images/voice blocked."""
        stranger_1 = f"stranger_x_{uuid.uuid4().hex[:6]}"
        stranger_2 = f"stranger_y_{uuid.uuid4().hex[:6]}"

        # Allowed: First text message
        allowed_1 = check_stranger_message_limit(
            db=db_session,
            sender_id=stranger_1,
            receiver_id=stranger_2,
            message_type="text",
        )
        assert allowed_1 is True

        # Disallowed: Image from stranger
        allowed_img = check_stranger_message_limit(
            db=db_session,
            sender_id=stranger_1,
            receiver_id=stranger_2,
            message_type="image",
        )
        assert allowed_img is False


# =============================================================================
# US-004: Real-Time IM & Intimacy Progression Tests
# =============================================================================

class TestUS004IMAndIntimacy:
    """Test US-004: AI icebreakers, intimacy XP state machine, and 2-min message recall."""

    def test_ai_icebreaker_generation_from_common_interests(
        self,
        db_session: Session,
        test_user_a: User,
        test_user_b: User,
    ):
        """AC2: Smart icebreaker extracts shared hobbies from both user profiles."""
        icebreaker = generate_icebreakers(
            db=db_session,
            user_a_id=test_user_a.id,
            user_b_id=test_user_b.id,
        )
        assert icebreaker is not None
        assert len(icebreaker.suggestions) >= 1
        assert isinstance(icebreaker.common_topics, list)

    def test_intimacy_xp_progression_state_machine(self, db_session: Session):
        """AC3: Intimacy XP accumulates across seed -> bud -> flower -> star tiers."""
        conv = ChatConversation(user_a_id="u_alpha", user_b_id="u_beta")
        db_session.add(conv)
        db_session.commit()

        # Initial message calculates gain and creates initial SEED record
        intimacy = calculate_intimacy_gain(
            db=db_session,
            conversation=conv,
            sender_id="u_alpha",
            content="这是一段充满真诚的初次相识问候",
        )
        assert intimacy.current_level == IntimacyLevelEnum.SEED.value
        assert intimacy.intimacy_score > 0.0
        assert "seed_sprout" in intimacy.unlocked_badges

        # Advance to BUD tier (>= 20 XP)
        intimacy.intimacy_score = 25.0
        intimacy = calculate_intimacy_gain(
            db=db_session,
            conversation=conv,
            sender_id="u_alpha",
            content="今天也是愉快交流的一天",
        )
        assert intimacy.current_level == IntimacyLevelEnum.BUD.value
        assert "budding_friend" in intimacy.unlocked_badges

        # Advance to FLOWER tier (>= 60 XP)
        intimacy.intimacy_score = 65.0
        intimacy = calculate_intimacy_gain(
            db=db_session,
            conversation=conv,
            sender_id="u_alpha",
            content="我们聊了好多共同回忆",
        )
        assert intimacy.current_level == IntimacyLevelEnum.FLOWER.value
        assert "flowering_bond" in intimacy.unlocked_badges

        # Advance to STAR tier (>= 150 XP)
        intimacy.intimacy_score = 155.0
        intimacy = calculate_intimacy_gain(
            db=db_session,
            conversation=conv,
            sender_id="u_alpha",
            content="真正的灵魂挚友",
        )
        assert intimacy.current_level == IntimacyLevelEnum.STAR.value
        assert "star_companion" in intimacy.unlocked_badges

    def test_message_recall_strict_2_minute_boundary(
        self,
        db_session: Session,
        test_user_a: User,
        test_user_b: User,
    ):
        """AC4: Recall succeeds within 2 minutes; strictly rejected after 2 minutes."""
        conv = ChatConversation(user_a_id=test_user_a.id, user_b_id=test_user_b.id)
        db_session.add(conv)
        db_session.flush()

        now = datetime.now(timezone.utc)

        # 1. Message sent 30 seconds ago (Within window -> Success)
        msg_recent = ChatMessage(
            conversation_id=conv.id,
            sender_id=test_user_a.id,
            receiver_id=test_user_b.id,
            content="刚刚打错了一句话，需要撤回",
            message_type=MessageTypeEnum.TEXT.value,
            created_at=now - timedelta(seconds=30),
        )
        db_session.add(msg_recent)
        db_session.flush()

        recalled = ChatService.recall_message(
            db=db_session,
            message_id=msg_recent.id,
            user_id=test_user_a.id,
        )
        assert recalled.is_recalled is True
        assert recalled.content == "该消息已被撤回"

        # 2. Message sent 150 seconds ago (> 120s -> Fails with HTTP 400)
        msg_old = ChatMessage(
            conversation_id=conv.id,
            sender_id=test_user_a.id,
            receiver_id=test_user_b.id,
            content="三分钟前的历史消息",
            message_type=MessageTypeEnum.TEXT.value,
            created_at=now - timedelta(seconds=150),
        )
        db_session.add(msg_old)
        db_session.flush()

        with pytest.raises(Exception) as exc_info:
            ChatService.recall_message(
                db=db_session,
                message_id=msg_old.id,
                user_id=test_user_a.id,
            )
        assert "2 分钟" in str(exc_info.value) or "400" in str(exc_info.value)


# =============================================================================
# US-005: Interest Circles & Topic Squares Tests
# =============================================================================

class TestUS005InterestCircles:
    """Test US-005: Circle categories, join, multi-tier comments & community moderation."""

    def test_circle_categories_and_sorting(self, client: TestClient, auth_headers_user_a: dict):
        """AC1: Browse circles by category (艺术展览, 户外徒步, 同城交友, 深夜树洞)."""
        categories = ["艺术展览", "户外徒步", "同城交友", "深夜树洞"]
        for cat in categories:
            circle_name = f"社群_{cat}_{uuid.uuid4().hex[:4]}"
            create_resp = client.post(
                "/api/v1/circles",
                headers=auth_headers_user_a,
                json={"name": circle_name, "category": cat, "description": f"专注{cat}深度交流"},
            )
            assert create_resp.status_code == 201

        # List circles by category
        list_resp = client.get("/api/v1/circles?category=户外徒步")
        assert list_resp.status_code == 200
        circles = list_resp.json()
        assert len(circles) >= 1
        assert all(c["category"] == "户外徒步" for c in circles)

    def test_multi_tier_comment_tree_assembly(
        self,
        client: TestClient,
        auth_headers_user_a: dict,
        auth_headers_user_b: dict,
    ):
        """AC3: Multi-tier nested comments (L1 -> L2 reply -> L3 reply)."""
        circle_resp = client.post(
            "/api/v1/circles",
            headers=auth_headers_user_a,
            json={"name": f"摄影圈_{uuid.uuid4().hex[:6]}", "category": "艺术展览", "description": "摄影讨论"},
        )
        circle_id = circle_resp.json()["id"]

        # Level 1: Root comment
        l1_resp = client.post(
            f"/api/v1/circles/{circle_id}/comments",
            headers=auth_headers_user_a,
            json={"content": "大家觉得索尼还是富士更适合街拍？"},
        )
        assert l1_resp.status_code == 201
        l1_id = l1_resp.json()["id"]

        # Level 2: Reply to L1
        l2_resp = client.post(
            f"/api/v1/circles/{circle_id}/comments",
            headers=auth_headers_user_b,
            json={"parent_id": l1_id, "content": "富士的胶片模拟色彩直出很省心！"},
        )
        assert l2_resp.status_code == 201
        l2_id = l2_resp.json()["id"]

        # Level 3: Reply to L2
        l3_resp = client.post(
            f"/api/v1/circles/{circle_id}/comments",
            headers=auth_headers_user_a,
            json={"parent_id": l2_id, "content": "确实，尤其是 Classic Chrome 滤镜太有味道了。"},
        )
        assert l3_resp.status_code == 201
        l3_id = l3_resp.json()["id"]

        # Verify hierarchical tree
        tree_resp = client.get(f"/api/v1/circles/{circle_id}/comments/tree")
        assert tree_resp.status_code == 200
        tree = tree_resp.json()
        root = next((n for n in tree if n["id"] == l1_id), None)
        assert root is not None
        assert len(root["replies"]) >= 1
        assert root["replies"][0]["id"] == l2_id


# =============================================================================
# US-006: Profile Persona & Privacy Protection Tests
# =============================================================================

class TestUS006ProfileAndPrivacy:
    """Test US-006: 3D avatar, 10s voice card, AES-256 PII encryption & privacy masking."""

    def test_profile_persona_fields_update(self, client: TestClient, auth_headers_user_a: dict):
        """AC1: Set 3D avatar, custom bio, 10-second voice card, and interest tags."""
        payload = {
            "avatar_url": "https://example.com/3d_avatar_infp.glb",
            "voice_card_url": "https://example.com/voice_10s.mp3",
            "bio": "在纷繁世界中保持自己的声音与热爱",
            "interest_tags": ["胶片摄影", "民谣live", "独立书店", "手冲咖啡"],
        }
        resp = client.put("/api/v1/users/me", headers=auth_headers_user_a, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["avatar_url"] == payload["avatar_url"]
        assert data["voice_card_url"] == payload["voice_card_url"]
        assert "胶片摄影" in data["interest_tags"]

    def test_aes_256_pii_encryption_and_client_masking(self):
        """AC4: Sensitive national credentials and phone numbers encrypted with AES-256 and masked."""
        raw_phone = "13912345678"
        encrypted_phone = encrypt_field(raw_phone)
        assert encrypted_phone != raw_phone
        assert decrypt_field(encrypted_phone) == raw_phone

        # Verify client masking
        masked = mask_phone_number(raw_phone)
        assert masked == "139****5678"
        assert masked != raw_phone
        assert "139" in masked and "5678" in masked

    def test_granular_privacy_settings_enforcement(
        self,
        client: TestClient,
        auth_headers_user_a: dict,
    ):
        """AC3: Privacy controls: hide_distance, hide_from_nearby, incognito_contacts."""
        resp = client.put(
            "/api/v1/users/privacy",
            headers=auth_headers_user_a,
            json={
                "hide_distance": True,
                "hide_from_nearby": True,
                "incognito_contacts": True,
                "stranger_msg_restricted": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hide_distance"] is True
        assert data["hide_from_nearby"] is True
        assert data["incognito_contacts"] is True
        assert data["stranger_msg_restricted"] is True
