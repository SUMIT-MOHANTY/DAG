"""Shared pytest fixtures for all test layers.

Provides:
- async SQLite in-memory database engine + session
- FastAPI TestClient (sync) and AsyncClient (async)
- Pre-seeded User fixtures (admin, operator, risk_manager)
- JWT token helpers
- Factory helpers for Restriction, Policy, Evidence, ApprovalRequest
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── App imports ───────────────────────────────────────────────────────────────
from backend.src.main import create_app
from backend.src.config.database import get_db
from backend.src.models.base import Base
from backend.src.models.user import User
from backend.src.models.policy import Policy
from backend.src.models.restriction import Restriction
from backend.src.models.evidence import Evidence, HashChainedAuditLog
from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.conversation import Conversation, Message
from backend.src.core.security import hash_password, create_access_token

# ── In-memory SQLite engine ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a shared in-memory SQLite engine for the test session."""
    _engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture()
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test session that rolls back after each test."""
    async_session = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session() as session:
        yield session
        await session.rollback()


# ── FastAPI app + dependency override ────────────────────────────────────────

@pytest_asyncio.fixture()
async def app(db_session: AsyncSession):
    """FastAPI app with DB dependency overridden to use the test session."""
    _app = create_app()

    async def _override_get_db():
        yield db_session

    _app.dependency_overrides[get_db] = _override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing FastAPI endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def admin_user(db_session: AsyncSession) -> User:
    """Create and persist an admin user."""
    user = User(
        id=str(uuid.uuid4()),
        email="admin@test.com",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def operator_user(db_session: AsyncSession) -> User:
    """Create and persist an operator user."""
    user = User(
        id=str(uuid.uuid4()),
        email="operator@test.com",
        hashed_password=hash_password("OperatorPass123!"),
        role="operator",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def risk_manager_user(db_session: AsyncSession) -> User:
    """Create and persist a risk manager user."""
    user = User(
        id=str(uuid.uuid4()),
        email="riskmanager@test.com",
        hashed_password=hash_password("RiskPass123!"),
        role="risk_manager",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ── Token helpers ─────────────────────────────────────────────────────────────

@pytest.fixture()
def admin_token(admin_user: User) -> str:
    return create_access_token(subject=admin_user.id, extra_claims={"role": admin_user.role})


@pytest.fixture()
def operator_token(operator_user: User) -> str:
    return create_access_token(subject=operator_user.id, extra_claims={"role": operator_user.role})


@pytest.fixture()
def risk_manager_token(risk_manager_user: User) -> str:
    return create_access_token(
        subject=risk_manager_user.id, extra_claims={"role": risk_manager_user.role}
    )


@pytest.fixture()
def expired_token(operator_user: User) -> str:
    """JWT token that is already expired."""
    return create_access_token(
        subject=operator_user.id,
        expires_delta=timedelta(seconds=-1),
    )


# ── Domain object factories ───────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def sample_policy(db_session: AsyncSession) -> Policy:
    """A valid, currently-active policy."""
    policy = Policy(
        id=str(uuid.uuid4()),
        name="Test Travel Policy v1",
        version="1.0",
        description="Integration test policy",
        effective_from=datetime.now(timezone.utc) - timedelta(days=30),
        effective_to=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(policy)
    await db_session.commit()
    await db_session.refresh(policy)
    return policy


@pytest_asyncio.fixture()
async def sample_restriction(db_session: AsyncSession, sample_policy: Policy) -> Restriction:
    """A low-risk restriction linked to sample_policy."""
    restriction = Restriction(
        id=str(uuid.uuid4()),
        name="Economy Class Only",
        description="Travelers must book economy class",
        rule_type="cabin_class",
        parameters={"allowed_classes": ["Y", "M"]},
        risk_level=2,
        source_policy_id=sample_policy.id,
        effective_from=datetime.now(timezone.utc) - timedelta(days=30),
        effective_to=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(restriction)
    await db_session.commit()
    await db_session.refresh(restriction)
    return restriction


@pytest_asyncio.fixture()
async def high_risk_restriction(db_session: AsyncSession, sample_policy: Policy) -> Restriction:
    """A high-risk restriction (risk_level=5) for exception-path tests."""
    restriction = Restriction(
        id=str(uuid.uuid4()),
        name="International Travel Ban",
        description="No international travel permitted",
        rule_type="destination",
        parameters={"blocked_regions": ["INTL"]},
        risk_level=5,
        source_policy_id=sample_policy.id,
        effective_from=datetime.now(timezone.utc) - timedelta(days=30),
        effective_to=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(restriction)
    await db_session.commit()
    await db_session.refresh(restriction)
    return restriction


@pytest_asyncio.fixture()
async def sample_evidence(db_session: AsyncSession, sample_restriction: Restriction) -> Evidence:
    """An evidence record linked to sample_restriction."""
    evidence = Evidence(
        id=str(uuid.uuid4()),
        restriction_id=sample_restriction.id,
        source_table="booking_records",
        source_record_id="BK-001",
        source_field="cabin_class",
        evidence_value="Business",
        confidence_score=0.92,
        collected_at=datetime.now(timezone.utc),
        row_version=1,
    )
    db_session.add(evidence)
    await db_session.commit()
    await db_session.refresh(evidence)
    return evidence


@pytest_asyncio.fixture()
async def pending_approval(db_session: AsyncSession, sample_restriction: Restriction) -> ApprovalRequest:
    """A pending approval request for sample_restriction."""
    ar = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=sample_restriction.id,
        risk_score=3.5,
        confidence_score=0.65,
        queue_type="low_confidence",
        priority="medium",
        status="pending",
        row_version=1,
    )
    db_session.add(ar)
    await db_session.commit()
    await db_session.refresh(ar)
    return ar


@pytest_asyncio.fixture()
async def high_risk_approval(db_session: AsyncSession, high_risk_restriction: Restriction) -> ApprovalRequest:
    """A pending high-risk approval request (queue_type=high_risk)."""
    ar = ApprovalRequest(
        id=str(uuid.uuid4()),
        restriction_query_id=high_risk_restriction.id,
        risk_score=4.8,
        confidence_score=0.55,
        queue_type="high_risk",
        priority="high",
        status="pending",
        row_version=1,
    )
    db_session.add(ar)
    await db_session.commit()
    await db_session.refresh(ar)
    return ar


@pytest_asyncio.fixture()
async def sample_conversation(db_session: AsyncSession, operator_user: User) -> Conversation:
    """An active conversation for operator_user."""
    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=operator_user.id,
        session_id=str(uuid.uuid4()),
        status="active",
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv
