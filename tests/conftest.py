"""Pytest fixtures providing in-memory async SQLite engine, test database sessions, and authenticated HTTP clients."""

import asyncio
from datetime import date, datetime
from typing import AsyncGenerator, Callable
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.database import Base, get_db
from src.main import app
from src.models.user import (
    User,
    EducationCredential,
    GenderEnum,
    DatingPreferenceEnum,
    VerificationStatusEnum,
    SchoolTierEnum,
    DegreeLevelEnum,
)
from src.core.security import hash_password, create_access_token


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create event loop for test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """In-memory async SQLite engine for isolated test runs."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Database session fixture bound to in-memory test engine."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Configures HTTPX AsyncClient with overridden get_db dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def auth_headers_factory() -> Callable[[User], dict]:
    """Generates Authorization header for a given user."""
    def _factory(user: User) -> dict:
        token = create_access_token(data={"sub": str(user.id), "email": user.email})
        return {"Authorization": f"Bearer {token}"}
    return _factory


@pytest_asyncio.fixture
def test_users_factory(db_session: AsyncSession):
    """Factory helper to rapidly construct verified or unverified test users in database."""
    async def _create_user(
        email: str,
        nickname: str = "TestUser",
        gender: GenderEnum = GenderEnum.MALE,
        preference: DatingPreferenceEnum = DatingPreferenceEnum.FEMALE,
        status: VerificationStatusEnum = VerificationStatusEnum.VERIFIED,
        reputation: float = 3.5,
        points: int = 100,
        city: str = "Beijing",
        birthdate: date = date(1998, 5, 20),
        school_tier: SchoolTierEnum = SchoolTierEnum.TIER_985,
        degree_level: DegreeLevelEnum = DegreeLevelEnum.MASTER,
        verified_at: datetime = None,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hash_password("Password123!"),
            nickname=nickname,
            birthdate=birthdate,
            resident_city=city,
            gender=gender,
            dating_preference=preference,
            interest_tags=["reading", "hiking", "travel"],
            verification_status=status,
            reputation_score=reputation,
            reputation_count=5 if status == VerificationStatusEnum.VERIFIED else 0,
            points_balance=points,
            is_active=True,
            verified_at=verified_at or (datetime.utcnow() if status == VerificationStatusEnum.VERIFIED else None),
            last_active_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.flush()

        if status == VerificationStatusEnum.VERIFIED or school_tier:
            cred = EducationCredential(
                user_id=user.id,
                credential_code=f"CODE-{user.id}",
                ocr_student_name=nickname,
                ocr_institution_name="Tsinghua University",
                school_tier=school_tier,
                degree_level=degree_level,
                ocr_confidence=0.98,
                requires_manual_audit=False,
                created_at=datetime.utcnow(),
            )
            db_session.add(cred)
            await db_session.flush()

        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user
