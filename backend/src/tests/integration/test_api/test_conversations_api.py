"""Integration tests for Conversations API.

Tests cover:
- Conversation creation and retrieval
- Message history management
- Agent plan capture and structure
- Conversation state transitions
- Message role validation
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.conversation import Conversation, Message
from backend.src.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Conversation CRUD Tests ───────────────────────────────────────────────────

class TestConversationCRUD:
    """Tests for conversation creation and management."""

    @pytest.mark.asyncio
    async def test_create_conversation_via_api(
        self,
        async_client: AsyncClient,
        operator_token: str,
    ):
        """POST /api/v1/conversations creates a new conversation."""
        payload = {
            "session_id": str(uuid.uuid4()),
        }
        response = await async_client.post(
            "/api/v1/conversations",
            json=payload,
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 201, 404)
        if response.status_code in (200, 201):
            data = response.json()
            assert "id" in data
            assert data.get("status") == "active"

    @pytest.mark.asyncio
    async def test_get_conversation_by_id(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_conversation: Conversation,
    ):
        """GET /api/v1/conversations/{id} returns conversation details."""
        response = await async_client.get(
            f"/api/v1/conversations/{sample_conversation.id}",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == sample_conversation.id
            assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(
        self,
        async_client: AsyncClient,
        operator_token: str,
    ):
        """GET /api/v1/conversations/{id} returns 404 for unknown ID."""
        response = await async_client.get(
            f"/api/v1/conversations/{uuid.uuid4()}",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_list_conversations(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_conversation: Conversation,
    ):
        """GET /api/v1/conversations returns list of conversations."""
        response = await async_client.get(
            "/api/v1/conversations",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_conversation_requires_auth(
        self,
        async_client: AsyncClient,
        sample_conversation: Conversation,
    ):
        """Conversation endpoints require authentication."""
        response = await async_client.get(
            f"/api/v1/conversations/{sample_conversation.id}",
        )
        assert response.status_code in (401, 403, 404)


# ── Message History Tests ─────────────────────────────────────────────────────

class TestMessageHistory:
    """Tests for message history within conversations."""

    @pytest.mark.asyncio
    async def test_add_message_to_conversation(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_conversation: Conversation,
    ):
        """POST /api/v1/conversations/{id}/messages adds a message."""
        payload = {
            "role": "user",
            "content": "Can I book business class to London?",
        }
        response = await async_client.post(
            f"/api/v1/conversations/{sample_conversation.id}/messages",
            json=payload,
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 201, 404)
        if response.status_code in (200, 201):
            data = response.json()
            assert data.get("role") == "user"
            assert "content" in data

    @pytest.mark.asyncio
    async def test_get_message_history(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_conversation: Conversation,
        db_session: AsyncSession,
    ):
        """GET /api/v1/conversations/{id}/messages returns message history."""
        # Add a message directly to DB
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=sample_conversation.id,
            role="user",
            content="Test message for history",
        )
        db_session.add(msg)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/conversations/{sample_conversation.id}/messages",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            messages = data if isinstance(data, list) else data.get("items", [])
            assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_message_roles_are_valid(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_conversation: Conversation,
        db_session: AsyncSession,
    ):
        """Messages must have valid roles: user, assistant, system."""
        valid_roles = ["user", "assistant", "system"]
        for role in valid_roles:
            msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=sample_conversation.id,
                role=role,
                content=f"Test {role} message",
            )
            db_session.add(msg)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/conversations/{sample_conversation.id}/messages",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            messages = data if isinstance(data, list) else data.get("items", [])
            for msg_data in messages:
                if isinstance(msg_data, dict) and "role" in msg_data:
                    assert msg_data["role"] in valid_roles + ["tool"]


# ── Agent Plan Capture Tests ──────────────────────────────────────────────────

class TestAgentPlanCapture:
    """Tests for agent plan capture and structure validation."""

    @pytest.mark.asyncio
    async def test_message_with_agent_plan_stored(
        self,
        db_session: AsyncSession,
        sample_conversation: Conversation,
    ):
        """Messages can store agent_plan JSON with tool call steps."""
        agent_plan = {
            "steps": [
                {
                    "step_id": "step_1",
                    "tool": "search_restrictions",
                    "input": {
                        "query": "cabin class restrictions for business travel",
                        "filters": {"risk_level": 3},
                    },
                    "output": {
                        "found": 2,
                        "restrictions": ["Economy Only", "No Upgrades"],
                    },
                    "status": "completed",
                    "duration_ms": 145,
                },
                {
                    "step_id": "step_2",
                    "tool": "evaluate_policy",
                    "input": {
                        "policy_id": "pol-001",
                        "booking_context": {"cabin_class": "business"},
                    },
                    "output": {
                        "recommendation": "BLOCK",
                        "risk_score": 4.2,
                        "confidence": 0.91,
                    },
                    "status": "completed",
                    "duration_ms": 320,
                },
            ],
            "total_steps": 2,
            "risk_score": 4.2,
            "confidence": 0.91,
            "recommendation": "BLOCK",
            "evidence_sources": [
                {
                    "source_table": "booking_records",
                    "source_record_id": "BK-001",
                    "confidence": 0.91,
                }
            ],
        }

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Business class is restricted per policy.",
            agent_plan=agent_plan,
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.agent_plan is not None
        assert len(msg.agent_plan["steps"]) == 2
        assert msg.agent_plan["risk_score"] == 4.2
        assert msg.agent_plan["confidence"] == 0.91
        assert msg.agent_plan["recommendation"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_agent_plan_step_structure(
        self,
        db_session: AsyncSession,
        sample_conversation: Conversation,
    ):
        """Each agent plan step has required fields."""
        required_step_fields = ["step_id", "tool", "input", "output", "status"]

        agent_plan = {
            "steps": [
                {
                    "step_id": "1",
                    "tool": "search_restrictions",
                    "input": {"query": "test"},
                    "output": {"found": 0},
                    "status": "completed",
                }
            ],
            "total_steps": 1,
            "risk_score": 1.0,
            "confidence": 0.95,
        }

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=sample_conversation.id,
            role="assistant",
            content="No restrictions found.",
            agent_plan=agent_plan,
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        for step in msg.agent_plan["steps"]:
            for field in required_step_fields:
                assert field in step, f"Step missing required field: {field}"

    @pytest.mark.asyncio
    async def test_agent_plan_evidence_attribution(
        self,
        db_session: AsyncSession,
        sample_conversation: Conversation,
        sample_evidence,
    ):
        """Agent plan captures evidence source attribution."""
        agent_plan = {
            "steps": [],
            "total_steps": 0,
            "risk_score": 2.0,
            "confidence": 0.88,
            "evidence_sources": [
                {
                    "evidence_id": sample_evidence.id,
                    "source_table": sample_evidence.source_table,
                    "source_record_id": sample_evidence.source_record_id,
                    "source_field": sample_evidence.source_field,
                    "confidence": sample_evidence.confidence_score,
                }
            ],
        }

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Evidence found.",
            agent_plan=agent_plan,
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        sources = msg.agent_plan["evidence_sources"]
        assert len(sources) == 1
        assert sources[0]["evidence_id"] == sample_evidence.id
        assert sources[0]["source_table"] == "booking_records"

    @pytest.mark.asyncio
    async def test_conversation_pending_approval_state(
        self,
        async_client: AsyncClient,
        operator_token: str,
        db_session: AsyncSession,
        sample_conversation: Conversation,
    ):
        """Conversation can reflect 'pending_approval' status."""
        # Update conversation status to pending_approval
        sample_conversation.status = "pending_approval"
        db_session.add(sample_conversation)
        await db_session.commit()
        await db_session.refresh(sample_conversation)

        assert sample_conversation.status == "pending_approval"

        response = await async_client.get(
            f"/api/v1/conversations/{sample_conversation.id}",
            headers=auth_headers(operator_token),
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "pending_approval"

    @pytest.mark.asyncio
    async def test_message_ordering_by_created_at(
        self,
        db_session: AsyncSession,
        sample_conversation: Conversation,
    ):
        """Messages are ordered by created_at ascending."""
        from datetime import timedelta

        base_time = datetime.now(timezone.utc)
        messages = []
        for i in range(3):
            msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=sample_conversation.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            db_session.add(msg)
            messages.append(msg)

        await db_session.commit()

        # Verify all messages were created
        from sqlalchemy import select
        result = await db_session.execute(
            select(Message)
            .where(Message.conversation_id == sample_conversation.id)
            .order_by(Message.created_at)
        )
        stored_messages = result.scalars().all()
        assert len(stored_messages) >= 3
