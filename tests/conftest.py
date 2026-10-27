"""Pytest global fixtures for SoulRed social platform.

Provides:
- In-memory SQLite isolated database session
- FastAPI TestClient with dependency overrides
- Seed test users (Alice & Bob) with persona profiles
- Signed JWT authorization headers
"""

from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import soulred.models  # Ensure all models are registered
from soulred.database import Base, get_db
from soulred.api.deps import get_db_session
from soulred.main import app
from soulred.models.user import User, UserProfile, PrivacySetting
from soulred.utils.crypto import hash_password, create_access_token

# In-memory SQLite with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in memory once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated transactional database session per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide FastAPI TestClient with database session dependency overridden."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_session] = override_get_db

    # Point ws_chat.SessionLocal to TestingSessionLocal for WebSocket threads
    import soulred.api.ws_chat as ws_module
    orig_session_local = ws_module.SessionLocal
    ws_module.SessionLocal = TestingSessionLocal

    with TestClient(app) as test_client:
        yield test_client

    ws_module.SessionLocal = orig_session_local
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_a(db_session: Session) -> User:
    """Create or return seeded test user Alice."""
    existing = db_session.query(User).filter(User.username == "alice_infp").first()
    if existing:
        return existing

    user = User(
        username="alice_infp",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        nickname="Alice in Wonderland",
        avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200",
        bio="热爱摄影、看展与独立民谣的 INFP 治愈系女生",
        gender="female",
        age=23,
        location="上海·徐汇",
        latitude=31.20,
        longitude=121.43,
        mbti="INFP",
        interest_tags=["艺术展览", "民谣音乐", "摄影日常"],
    )
    db_session.add(profile)

    privacy = PrivacySetting(
        user_id=user.id,
        hide_distance=False,
        hide_from_nearby=False,
        incognito_contacts=False,
        stranger_msg_restricted=True,
    )
    db_session.add(privacy)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_b(db_session: Session) -> User:
    """Create or return seeded test user Bob."""
    existing = db_session.query(User).filter(User.username == "bob_enfj").first()
    if existing:
        return existing

    user = User(
        username="bob_enfj",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        nickname="Bob Wanderer",
        avatar_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200",
        bio="ENFJ 户外吉他手，寻找有共鸣的灵魂伙伴",
        gender="male",
        age=25,
        location="上海·静安",
        latitude=31.23,
        longitude=121.45,
        mbti="ENFJ",
        interest_tags=["民谣音乐", "户外徒步", "摄影日常"],
    )
    db_session.add(profile)

    privacy = PrivacySetting(
        user_id=user.id,
        hide_distance=False,
        hide_from_nearby=False,
        incognito_contacts=False,
        stranger_msg_restricted=True,
    )
    db_session.add(privacy)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user_a(test_user_a: User) -> dict:
    """Return HTTP Authorization header for test user Alice."""
    token = create_access_token(
        data={"sub": test_user_a.id, "username": test_user_a.username}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b(test_user_b: User) -> dict:
    """Return HTTP Authorization header for test user Bob."""
    token = create_access_token(
        data={"sub": test_user_b.id, "username": test_user_b.username}
    )
    return {"Authorization": f"Bearer {token}"}
