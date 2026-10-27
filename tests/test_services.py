"""Unit test suite for SoulRed core domain services and algorithms.

Covers:
- Soul multidimensional vector cosine similarity & MBTI synergy bonuses
- Xiaohongshu waterfall feed aspect ratio pre-calculation & skeleton colors
- Chat intimacy XP progression state machine & tier promotion
- AI content safety keyword interception & suspicious pattern escalation
- Stranger anti-harassment quota and message type restrictions
- Registration, authentication, verification badges, and privacy masking
- Rich post creation, draft auto-save, like toggles, and detail view assembly
- QingTeng daily recommendation cards and bidirectional mutual crush state transition
- AI icebreaker topic generation and 2-minute message recall
- Circle memberships, threaded comment trees, and content moderation
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from soulred.database import Base
from soulred.models.user import User, UserProfile, VerificationBadge, PrivacySetting
from soulred.models.post import Post, PostImage, PostDraft, AspectRatioEnum, PostStatusEnum
from soulred.models.match import PersonalityQuizResult, DailyRecommendation, CrushMatch, CrushStatusEnum
from soulred.models.chat import ChatConversation, ChatMessage, IntimacyRecord, IntimacyLevelEnum, MessageTypeEnum
from soulred.models.circle import InterestCircle, CircleMember, CircleComment, CircleCategoryEnum
from soulred.schemas.user import UserCreate, VerificationSubmitSchema
from soulred.schemas.post import PostCreate, PostImageSchema, PostDraftSave
from soulred.schemas.circle import CommentCreateSchema, ModerationActionSchema
from soulred.services.safety_service import (
    ContentSafetyService,
    check_text_safety,
    check_image_safety,
    review_post_content,
)
from soulred.services.auth_service import AuthService
from soulred.services.post_service import PostService
from soulred.services.feed_service import (
    FeedService,
    calculate_card_aspect_ratio,
    get_waterfall_feed,
    rank_feed_items,
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
from soulred.services.circle_service import CircleService


@pytest.fixture
def db_session():
    """Create an isolated, fresh in-memory SQLite database session for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


# =============================================================================
# 1. SPECIFICATION-REQUIRED TESTS
# =============================================================================

def test_soul_similarity_calc():
    """Verify Soul multidimensional vector cosine similarity & MBTI synergy bonuses."""
    # Test identical vectors -> similarity = 1.0
    vec1 = [0.8, 0.7, 0.9, 0.6, 0.85]
    sim_identical = calculate_soul_similarity(vec1, vec1)
    assert sim_identical >= 0.99

    # Test orthogonal/dissimilar vectors
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    sim_ortho = calculate_soul_similarity(vec_a, vec_b)
    assert sim_ortho == 0.0

    # Test MBTI golden pair synergy bonus
    sim_golden = calculate_soul_similarity(
        vector_a=[0.8, 0.4, 0.6, 0.5],
        vector_b=[0.6, 0.7, 0.5, 0.8],
        mbti_a="INFP",
        mbti_b="ENFJ",
    )
    sim_neutral = calculate_soul_similarity(
        vector_a=[0.8, 0.4, 0.6, 0.5],
        vector_b=[0.6, 0.7, 0.5, 0.8],
        mbti_a="INFP",
        mbti_b="ISTP",
    )
    # Golden pair should yield higher compatibility
    assert sim_golden > sim_neutral


def test_waterfall_card_aspect_ratio():
    """Verify waterfall card aspect ratio calculation and skeleton styling."""
    # Standard presets
    h_1_1, color_1_1 = calculate_card_aspect_ratio("1:1")
    assert h_1_1 == 260
    assert color_1_1 == "#fef2f2"

    h_3_4, color_3_4 = calculate_card_aspect_ratio("3:4")
    assert h_3_4 == 340
    assert color_3_4 == "#f3f4f6"

    h_4_3, color_4_3 = calculate_card_aspect_ratio("4:3")
    assert h_4_3 == 200
    assert color_4_3 == "#f0fdf4"

    # Custom dynamic calculation
    h_custom, color_custom = calculate_card_aspect_ratio("custom", width=1000, height=1500)
    assert 180 <= h_custom <= 420
    assert color_custom == "#eff6ff"


def test_intimacy_xp_progression(db_session: Session):
    """Verify Soul intimacy XP accumulation and tier unlocking state machine."""
    # Setup conversation
    conv = ChatConversation(
        user_a_id="user-1",
        user_b_id="user-2",
        is_stranger_session=False,
    )
    db_session.add(conv)
    db_session.commit()

    # Initial gain with short message
    intimacy = calculate_intimacy_gain(
        db=db_session,
        conversation=conv,
        sender_id="user-1",
        content="Hello there!",
    )
    assert intimacy.current_level == IntimacyLevelEnum.SEED.value
    assert intimacy.interaction_days == 1
    assert "seed_sprout" in intimacy.unlocked_badges

    # Accumulate score to transition to BUD tier (>= 20 XP)
    intimacy.intimacy_score = 25.0
    intimacy = calculate_intimacy_gain(
        db=db_session,
        conversation=conv,
        sender_id="user-1",
        content="Chatting more",
    )
    assert intimacy.current_level == IntimacyLevelEnum.BUD.value
    assert "budding_friend" in intimacy.unlocked_badges

    # Transition to FLOWER tier (>= 60 XP)
    intimacy.intimacy_score = 65.0
    intimacy = calculate_intimacy_gain(
        db=db_session,
        conversation=conv,
        sender_id="user-1",
        content="Deep conversation",
    )
    assert intimacy.current_level == IntimacyLevelEnum.FLOWER.value
    assert "flowering_bond" in intimacy.unlocked_badges

    # Transition to STAR tier (>= 150 XP)
    intimacy.intimacy_score = 155.0
    intimacy = calculate_intimacy_gain(
        db=db_session,
        conversation=conv,
        sender_id="user-1",
        content="Best friends forever",
    )
    assert intimacy.current_level == IntimacyLevelEnum.STAR.value
    assert "star_companion" in intimacy.unlocked_badges


def test_safety_keyword_interception():
    """Verify AI sensitive keyword interception and text masking."""
    # Prohibited porn/scam keywords
    unsafe_text = "加微信详谈，提供刷单兼职日赚500，还有裸聊服务"
    res = check_text_safety(unsafe_text)
    assert res["is_safe"] is False
    assert res["action"] == "REJECTED"
    assert len(res["violations"]) > 0
    assert "*" in res["filtered_text"]

    # Suspicious pattern -> PENDING_REVIEW
    suspicious_text = "请关注我的微信号，我们一起学习交流"
    res_susp = check_text_safety(suspicious_text)
    assert res_susp["action"] == "PENDING_REVIEW"

    # Clean text -> APPROVED
    clean_text = "今天在当代艺术馆看展，被这幅光影装置深深治愈了！"
    res_clean = check_text_safety(clean_text)
    assert res_clean["is_safe"] is True
    assert res_clean["action"] == "APPROVED"
    assert len(res_clean["violations"]) == 0

    # Image safety check
    assert check_image_safety("https://cdn.example.com/nsfw_leak.jpg")["action"] == "REJECTED"
    assert check_image_safety("https://cdn.example.com/art_exhibit.jpg")["action"] == "APPROVED"


def test_stranger_greeting_quota(db_session: Session):
    """Verify stranger single-message quota and anti-harassment limits."""
    user_a = "user-alice"
    user_b = "user-bob"

    # 1. Non-text message from stranger is immediately rejected
    can_send_voice = check_stranger_message_limit(
        db=db_session,
        sender_id=user_a,
        receiver_id=user_b,
        message_type="voice",
    )
    assert can_send_voice is False

    can_send_img = check_stranger_message_limit(
        db=db_session,
        sender_id=user_a,
        receiver_id=user_b,
        message_type="image",
    )
    assert can_send_img is False

    # 2. First text message is permitted
    can_send_first_text = check_stranger_message_limit(
        db=db_session,
        sender_id=user_a,
        receiver_id=user_b,
        message_type="text",
    )
    assert can_send_first_text is True

    # Record first message sent today
    conv = ChatConversation(user_a_id=user_a, user_b_id=user_b, is_stranger_session=True)
    db_session.add(conv)
    db_session.flush()

    msg = ChatMessage(
        conversation_id=conv.id,
        sender_id=user_a,
        receiver_id=user_b,
        message_type="text",
        content="Hi Bob! Nice to meet you.",
    )
    db_session.add(msg)
    db_session.commit()

    # 3. Second text message on the same day is BLOCKED
    can_send_second_text = check_stranger_message_limit(
        db=db_session,
        sender_id=user_a,
        receiver_id=user_b,
        message_type="text",
    )
    assert can_send_second_text is False


# =============================================================================
# 2. ADDITIONAL END-TO-END DOMAIN SERVICE TESTS
# =============================================================================

def test_auth_service_registration_and_login(db_session: Session):
    """Verify user registration, AES phone encryption, and login authentication."""
    user_in = UserCreate(
        username="celeste",
        password="securePassword123!",
        phone="13800138000",
        nickname="Celeste Star",
        gender="female",
        mbti="INFP",
    )

    user = AuthService.register_user(db_session, user_in)
    assert user.id is not None
    assert user.username == "celeste"
    assert user.phone_encrypted is not None
    assert user.phone_encrypted != "13800138000"  # Must be AES encrypted
    assert user.profile.nickname == "Celeste Star"
    assert user.profile.mbti == "INFP"

    # Authenticate successfully
    auth_user = AuthService.authenticate_user(db_session, "celeste", "securePassword123!")
    assert auth_user is not None
    assert auth_user.id == user.id

    # Wrong password failure
    failed_user = AuthService.authenticate_user(db_session, "celeste", "wrongPassword")
    assert failed_user is None


def test_auth_service_verification_and_privacy(db_session: Session):
    """Verify credential verification submission and privacy coordinate masking."""
    user_in = UserCreate(username="david", password="password123")
    user = AuthService.register_user(db_session, user_in)

    # Submit verification credentials
    ver_in = VerificationSubmitSchema(
        badge_type="education",
        school="Tsinghua University",
        degree="Master",
        real_name="David Zhang",
        id_card="110101199001011234",
    )
    badge = AuthService.submit_verification(db_session, user.id, ver_in)
    assert badge.badge_type == "education"
    assert badge.education_school == "Tsinghua University"
    assert badge.real_name_encrypted is not None

    # Privacy filtering
    user.profile.latitude = 31.2304
    user.profile.longitude = 121.4737
    user.profile.location = "上海市黄浦区"
    user.privacy_setting.hide_distance = True

    filtered_info = AuthService.apply_privacy_filters(
        viewer_user_id="other-user",
        target_profile=user.profile,
        privacy=user.privacy_setting,
        viewer_lat=31.2200,
        viewer_lon=121.4600,
    )
    assert filtered_info["distance_km"] is None  # Distance is hidden per privacy setting


def test_post_creation_and_like_toggle(db_session: Session):
    """Verify rich note publishing, image attachments, and atomic like toggles."""
    author_in = UserCreate(username="emily", password="password123")
    author = AuthService.register_user(db_session, author_in)

    post_in = PostCreate(
        title="周末治愈系露营分享",
        content="逃离城市喧嚣，在山谷间呼吸清新的风，太治愈了！",
        mood_tag="治愈中",
        topics=["露营", "户外生活"],
        channel="recommend",
        images=[
            PostImageSchema(
                image_url="https://images.unsplash.com/photo-1504280390367-361c6d9f38f4",
                aspect_ratio="3:4",
                order_index=0,
            )
        ],
    )

    post = PostService.create_post(db_session, author.id, post_in)
    assert post.id is not None
    assert post.title == "周末治愈系露营分享"
    assert len(post.images) == 1
    assert post.likes_count == 0

    # Toggle like -> ON
    like_res1 = PostService.toggle_like(db_session, author.id, post.id)
    assert like_res1.is_liked is True
    assert like_res1.likes_count == 1

    # Toggle like -> OFF
    like_res2 = PostService.toggle_like(db_session, author.id, post.id)
    assert like_res2.is_liked is False
    assert like_res2.likes_count == 0

    # Draft save and get
    draft_in = PostDraftSave(title="草稿标题", content="草稿正文", topics=["草稿"])
    PostService.save_draft(db_session, author.id, draft_in)
    draft = PostService.get_draft(db_session, author.id)
    assert draft is not None
    assert draft.title == "草稿标题"


def test_feed_service_waterfall(db_session: Session):
    """Verify waterfall cards assembly and multi-channel feed distribution."""
    author = AuthService.register_user(
        db_session,
        UserCreate(username="frank", password="password123", nickname="Frankie"),
    )

    post_in = PostCreate(
        title="摄影作品展",
        content="黑白光影的魅力",
        channel="recommend",
        images=[
            PostImageSchema(
                image_url="https://images.unsplash.com/photo-1517841905240-472988babdf9",
                aspect_ratio="3:4",
            )
        ],
    )
    post = PostService.create_post(db_session, author.id, post_in)

    feed_cards = FeedService.get_waterfall_feed(
        db=db_session,
        channel="recommend",
        current_user_id=author.id,
    )
    assert len(feed_cards) >= 1
    card = feed_cards[0]
    assert card.title == "摄影作品展"
    assert card.author_nickname == "Frankie"
    assert card.aspect_ratio == "3:4"
    assert card.card_height == 340


def test_matching_service_crush_flow(db_session: Session):
    """Verify mutual crush state transition and auto-establishment of chat session."""
    user1 = AuthService.register_user(db_session, UserCreate(username="greg", password="password123"))
    user2 = AuthService.register_user(db_session, UserCreate(username="helen", password="password123"))

    # User 1 crushes on User 2 -> PENDING
    res1 = MatchingService.handle_crush_action(db_session, user1.id, user2.id, "crush")
    assert res1.is_mutual is False
    assert res1.status == CrushStatusEnum.PENDING.value

    # User 2 crushes on User 1 -> MUTUAL MATCH (双向奔赴)
    res2 = MatchingService.handle_crush_action(db_session, user2.id, user1.id, "crush")
    assert res2.is_mutual is True
    assert res2.status == CrushStatusEnum.MUTUAL.value
    assert res2.conversation_id is not None

    # Inspect auto-created ChatConversation
    conv = db_session.query(ChatConversation).filter(ChatConversation.id == res2.conversation_id).first()
    assert conv is not None
    assert conv.is_stranger_session is False


def test_chat_service_and_message_recall(db_session: Session):
    """Verify message recording, icebreaker generation, and 2-minute message recall."""
    user1 = AuthService.register_user(
        db_session,
        UserCreate(username="ian", password="password123", mbti="INTJ"),
    )
    user2 = AuthService.register_user(
        db_session,
        UserCreate(username="julia", password="password123", mbti="ENFP"),
    )

    # Set interest tags
    user1.profile.interest_tags = ["艺术展览", "独立电影"]
    user2.profile.interest_tags = ["艺术展览", "户外徒步"]
    db_session.commit()

    # Icebreaker suggestions
    icebreakers = ChatService.generate_icebreakers(db_session, user1.id, user2.id)
    assert len(icebreakers.suggestions) > 0
    assert "艺术展览" in icebreakers.common_topics

    # Record message (First message between strangers)
    msg = ChatService.record_message(
        db=db_session,
        sender_id=user1.id,
        receiver_id=user2.id,
        content="你好，看到你也常去上海看展！",
        message_type="text",
    )
    assert msg.id is not None
    assert msg.content == "你好，看到你也常去上海看展！"

    # Recall within 2 minutes succeeds
    recalled = ChatService.recall_message(db_session, msg.id, user1.id)
    assert recalled.is_recalled is True
    assert recalled.content == "该消息已被撤回"


def test_circle_service_comment_tree(db_session: Session):
    """Verify interest circles, comment posting, and nested comment tree building."""
    user = AuthService.register_user(db_session, UserCreate(username="kevin", password="password123"))

    # Create Circle
    circle = InterestCircle(
        name="青年艺术沙龙",
        category=CircleCategoryEnum.ART.value,
        description="专注先锋艺术与展览交流",
        owner_id=user.id,
    )
    db_session.add(circle)
    db_session.commit()

    # Join circle
    member = CircleService.join_circle(db_session, user.id, circle.id)
    assert member is not None
    assert member.circle_id == circle.id

    # Post root comment
    root_comment = CircleService.post_comment(
        db_session,
        user.id,
        CommentCreateSchema(
            circle_id=circle.id,
            content="下周西岸美术馆有新展，有人一起去吗？",
        ),
    )
    assert root_comment.id is not None

    # Post reply comment
    reply_comment = CircleService.post_comment(
        db_session,
        user.id,
        CommentCreateSchema(
            circle_id=circle.id,
            parent_id=root_comment.id,
            content="我也打算去，可以组个队！",
        ),
    )
    assert reply_comment.id is not None
    assert reply_comment.parent_id == root_comment.id

    # Build tree
    all_comments = db_session.query(CircleComment).filter(CircleComment.circle_id == circle.id).all()
    tree = CircleService.build_comment_tree(all_comments)
    assert len(tree) == 1
    assert tree[0].id == root_comment.id
    assert len(tree[0].replies) == 1
    assert tree[0].replies[0].id == reply_comment.id
