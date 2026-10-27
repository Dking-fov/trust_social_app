"""Unit and integration tests for ORM models, relationships, and cryptographic tools."""

import uuid
from sqlalchemy.orm import Session

from soulred.models.user import (
    User,
    UserProfile,
    VerificationBadge,
    PrivacySetting,
    VerificationStatusEnum,
    GenderEnum,
)
from soulred.models.post import (
    Post,
    PostImage,
    PostLike,
    PostDraft,
    AspectRatioEnum,
    PostStatusEnum,
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
from soulred.utils.crypto import (
    encrypt_field,
    decrypt_field,
    hash_password,
    verify_password,
)


def test_crypto_aes_gcm():
    """Verify AES-256-GCM encryption and decryption round-trip integrity."""
    # Plain text samples (sensitive PII)
    sample_phone = "13812345678"
    sample_id_card = "310101199801011234"
    sample_name = "张三丰"

    # Encrypt
    encrypted_phone = encrypt_field(sample_phone)
    encrypted_id = encrypt_field(sample_id_card)
    encrypted_name = encrypt_field(sample_name)

    assert encrypted_phone is not None
    assert encrypted_phone != sample_phone
    assert encrypted_id != sample_id_card
    assert encrypted_name != sample_name

    # Decrypt
    decrypted_phone = decrypt_field(encrypted_phone)
    decrypted_id = decrypt_field(encrypted_id)
    decrypted_name = decrypt_field(encrypted_name)

    assert decrypted_phone == sample_phone
    assert decrypted_id == sample_id_card
    assert decrypted_name == sample_name

    # Edge cases
    assert encrypt_field(None) is None
    assert decrypt_field(None) is None
    assert encrypt_field("") == ""
    assert decrypt_field("") == ""

    # Password hash verification
    pwd = "MySecretPassword123"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_user_model_creation(db_session: Session):
    """Verify User ORM entity creation with 1:1 profile and privacy relationships."""
    unique_name = f"user_{uuid.uuid4().hex[:8]}"
    raw_phone = "13900001111"
    enc_phone = encrypt_field(raw_phone)

    user = User(
        username=unique_name,
        phone_encrypted=enc_phone,
        hashed_password=hash_password("SecuredPwd!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        nickname="Super Star",
        gender=GenderEnum.FEMALE.value,
        age=22,
        location="上海·静安",
        mbti="ENFP",
        interest_tags=["摇滚乐", "胶片摄影"],
    )
    db_session.add(profile)

    privacy = PrivacySetting(
        user_id=user.id,
        hide_distance=True,
        hide_from_nearby=False,
    )
    db_session.add(privacy)

    badge = VerificationBadge(
        user_id=user.id,
        badge_type="education",
        education_school="复旦大学",
        education_degree="硕士",
        status=VerificationStatusEnum.APPROVED.value,
    )
    db_session.add(badge)

    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.profile is not None
    assert user.profile.nickname == "Super Star"
    assert user.profile.mbti == "ENFP"
    assert user.privacy_setting.hide_distance is True
    assert len(user.verification_badges) == 1
    assert user.verification_badges[0].education_school == "复旦大学"
    assert decrypt_field(user.phone_encrypted) == raw_phone


def test_post_image_relationships(db_session: Session, test_user_a: User):
    """Verify Post entity, multi-image attachments, draft, and like cascade relationships."""
    post = Post(
        author_id=test_user_a.id,
        title="上海看展日常 ✨",
        content="西岸美术馆的光影真的太美了，推荐大家周末打卡！",
        mood_tag="治愈中",
        topics=["看展", "周末去哪儿"],
        channel="recommend",
        status=PostStatusEnum.PUBLISHED.value,
    )
    db_session.add(post)
    db_session.flush()

    img1 = PostImage(
        post_id=post.id,
        image_url="https://example.com/img1.jpg",
        order_index=0,
        aspect_ratio=AspectRatioEnum.RATIO_3_4.value,
        width=1080,
        height=1440,
    )
    img2 = PostImage(
        post_id=post.id,
        image_url="https://example.com/img2.jpg",
        order_index=1,
        aspect_ratio=AspectRatioEnum.RATIO_1_1.value,
        width=1080,
        height=1080,
    )
    db_session.add_all([img1, img2])

    like = PostLike(
        post_id=post.id,
        user_id=test_user_a.id,
    )
    db_session.add(like)

    # Test draft auto-save
    draft = PostDraft(
        user_id=test_user_a.id,
        title="未完成的胶片随笔",
        content="在胶片机里留存的秋天...",
    )
    db_session.add(draft)

    db_session.commit()
    db_session.refresh(post)

    assert post.id is not None
    assert len(post.images) == 2
    assert post.images[0].aspect_ratio == "3:4"
    assert len(post.likes) == 1
    assert post.likes[0].user_id == test_user_a.id


def test_chat_intimacy_relationships(db_session: Session, test_user_a: User, test_user_b: User):
    """Verify ChatConversation, message exchange, and Soul intimacy progression model."""
    conv = ChatConversation(
        user_a_id=test_user_a.id,
        user_b_id=test_user_b.id,
        last_message_content="Hi Alice, 很高兴在 SoulRed 认识你！",
        is_stranger_session=False,
    )
    db_session.add(conv)
    db_session.flush()

    msg1 = ChatMessage(
        conversation_id=conv.id,
        sender_id=test_user_b.id,
        receiver_id=test_user_a.id,
        message_type=MessageTypeEnum.TEXT.value,
        content="Hi Alice, 很高兴在 SoulRed 认识你！",
    )
    msg2 = ChatMessage(
        conversation_id=conv.id,
        sender_id=test_user_a.id,
        receiver_id=test_user_b.id,
        message_type=MessageTypeEnum.TEXT.value,
        content="你好 Bob！你也常看摇滚现场吗？",
    )
    db_session.add_all([msg1, msg2])

    intimacy = IntimacyRecord(
        conversation_id=conv.id,
        user_a_id=test_user_a.id,
        user_b_id=test_user_b.id,
        intimacy_score=25.0,
        current_level=IntimacyLevelEnum.BUD.value,
        interaction_days=2,
        unlocked_badges=["seed_sprout", "budding_friend"],
    )
    db_session.add(intimacy)

    db_session.commit()
    db_session.refresh(conv)

    assert conv.id is not None
    assert len(conv.messages) == 2
    assert conv.intimacy is not None
    assert conv.intimacy.intimacy_score == 25.0
    assert conv.intimacy.current_level == "渐入佳境"
