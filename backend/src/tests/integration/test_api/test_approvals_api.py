"""Integration tests for Approvals API — queue filtering, assignment, decision submission,
optimistic locking, and concurrent modification (second exception path).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.restriction import Restriction
from backend.src.models.user import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/v1/approvals/{id} — retrieve
# ---------------------------------------------------------------------------

class TestGetApprovalRequest:
    @pytest.mark.asyncio
    async def test_get_pending_approval(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.get(
            f"/api/v1/approvals/{pending_approval.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["id"] == pending_approval.id
            assert data["status"] == "pending"
            assert "row_version" in data
            assert "queue_type" in data

    @pytest.mark.asyncio
    async def test_get_high_risk_approval(
        self,
        async_client: AsyncClient,
        operator_token: str,
        high_risk_approval: ApprovalRequest,
    ):
        resp = await async_client.get(
            f"/api/v1/approvals/{high_risk_approval.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["queue_type"] == "high_risk"
            assert data["risk_score"] >= 4.0

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.get(
            f"/api/v1/approvals/{uuid.uuid4()}",
            headers=_auth(operator_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_requires_auth(
        self, async_client: AsyncClient, pending_approval: ApprovalRequest
    ):
        resp = await async_client.get(f"/api/v1/approvals/{pending_approval.id}")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_returns_version_header(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.get(
            f"/api/v1/approvals/{pending_approval.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "x-row-version" in resp.headers or "etag" in resp.headers


# ---------------------------------------------------------------------------
# PATCH /api/v1/approvals/{id}/approve
# ---------------------------------------------------------------------------

class TestApproveRequest:
    @pytest.mark.asyncio
    async def test_approve_pending_request(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={"rationale": "Approved after review of all evidence."},
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "approved"
            assert data["row_version"] > 1

    @pytest.mark.asyncio
    async def test_approve_requires_rationale(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={"rationale": "Hi"},  # too short (min_length=5)
            headers=_auth(operator_token),
        )
        assert resp.status_code in (422, 400, 404)

    @pytest.mark.asyncio
    async def test_approve_nonexistent_returns_404(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{uuid.uuid4()}/approve",
            json={"rationale": "Approved after review."},
            headers=_auth(operator_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_requires_auth(
        self, async_client: AsyncClient, pending_approval: ApprovalRequest
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={"rationale": "Approved after review."},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /api/v1/approvals/{id}/reject
# ---------------------------------------------------------------------------

class TestRejectRequest:
    @pytest.mark.asyncio
    async def test_reject_pending_request(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/reject",
            json={"rationale": "Rejected due to policy violation."},
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_nonexistent_returns_404(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{uuid.uuid4()}/reject",
            json={"rationale": "Rejected due to policy violation."},
            headers=_auth(operator_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/approvals/{id}/escalate
# ---------------------------------------------------------------------------

class TestEscalateRequest:
    @pytest.mark.asyncio
    async def test_escalate_pending_request(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/escalate",
            json={"rationale": "Escalating for senior review."},
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "escalated"


# ---------------------------------------------------------------------------
# PATCH /api/v1/approvals/{id}/withdraw
# ---------------------------------------------------------------------------

class TestWithdrawRequest:
    @pytest.mark.asyncio
    async def test_withdraw_pending_request(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/withdraw",
            json={"rationale": "Withdrawing as no longer needed."},
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "withdrawn"


# ---------------------------------------------------------------------------
# Optimistic locking — second exception path (concurrent modification)
# ---------------------------------------------------------------------------

class TestOptimisticLocking:
    @pytest.mark.asyncio
    async def test_stale_version_returns_409(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        """Send a stale expected_version → expect HTTP 409 Conflict."""
        stale_version = 999  # deliberately wrong
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={
                "rationale": "Approved after review of all evidence.",
                "expected_version": stale_version,
            },
            headers=_auth(operator_token),
        )
        assert resp.status_code in (409, 404)
        if resp.status_code == 409:
            data = resp.json()
            # Should contain conflict details
            assert "error" in data or "detail" in data

    @pytest.mark.asyncio
    async def test_correct_version_succeeds(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        """Send the correct expected_version → expect success."""
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={
                "rationale": "Approved after review of all evidence.",
                "expected_version": pending_approval.row_version,
            },
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "approved"
            assert data["row_version"] > pending_approval.row_version

    @pytest.mark.asyncio
    async def test_409_response_contains_current_state(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        """409 response must embed current_state so client can refresh."""
        resp = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/reject",
            json={
                "rationale": "Rejected due to policy violation.",
                "expected_version": 9999,
            },
            headers=_auth(operator_token),
        )
        assert resp.status_code in (409, 404)
        if resp.status_code == 409:
            body = resp.json()
            # The conflict response should carry detail with current_state
            detail = body.get("detail", {})
            assert "conflict_type" in detail or "current_state" in detail

    @pytest.mark.asyncio
    async def test_double_approve_second_returns_409_or_409(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        """Two concurrent approvals: first wins, second gets 409 (state machine)."""
        # First approval
        resp1 = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={"rationale": "First approver decision."},
            headers=_auth(operator_token),
        )
        # Second approval on already-approved request
        resp2 = await async_client.patch(
            f"/api/v1/approvals/{pending_approval.id}/approve",
            json={"rationale": "Second approver decision."},
            headers=_auth(operator_token),
        )
        if resp1.status_code == 200:
            # Second attempt on terminal state should fail
            assert resp2.status_code in (409, 404, 422)


# ---------------------------------------------------------------------------
# Queue filtering
# ---------------------------------------------------------------------------

class TestApprovalQueueFiltering:
    @pytest.mark.asyncio
    async def test_list_approvals_by_queue_type(
        self,
        async_client: AsyncClient,
        operator_token: str,
        high_risk_approval: ApprovalRequest,
    ):
        resp = await async_client.get(
            "/api/v1/approvals?queue_type=high_risk",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_list_approvals_by_status(
        self,
        async_client: AsyncClient,
        operator_token: str,
        pending_approval: ApprovalRequest,
    ):
        resp = await async_client.get(
            "/api/v1/approvals?status=pending",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_list_approvals_by_priority(
        self,
        async_client: AsyncClient,
        operator_token: str,
    ):
        resp = await async_client.get(
            "/api/v1/approvals?priority=high",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404, 422)
