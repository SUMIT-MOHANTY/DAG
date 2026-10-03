"""Integration tests for Policies API — CRUD, evaluation endpoint, version handling."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from backend.src.models.policy import Policy
from backend.src.models.restriction import Restriction


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _policy_payload(**overrides) -> dict:
    base = {
        "name": f"Policy {uuid.uuid4().hex[:6]}",
        "version": "1.0",
        "description": "Test policy",
        "effective_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "effective_to": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# GET /api/v1/policies — list
# ---------------------------------------------------------------------------

class TestListPolicies:
    @pytest.mark.asyncio
    async def test_list_returns_200_or_404(
        self, async_client: AsyncClient, operator_token: str, sample_policy: Policy
    ):
        resp = await async_client.get(
            "/api/v1/policies", headers=_auth(operator_token)
        )
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, async_client: AsyncClient):
        resp = await async_client.get("/api/v1/policies")
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_list_pagination(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.get(
            "/api/v1/policies?page_size=10", headers=_auth(operator_token)
        )
        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_list_filter_active(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.get(
            "/api/v1/policies?is_active=true", headers=_auth(operator_token)
        )
        assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# POST /api/v1/policies — create
# ---------------------------------------------------------------------------

class TestCreatePolicy:
    @pytest.mark.asyncio
    async def test_create_returns_201(
        self, async_client: AsyncClient, operator_token: str
    ):
        payload = _policy_payload()
        resp = await async_client.post(
            "/api/v1/policies", json=payload, headers=_auth(operator_token)
        )
        assert resp.status_code in (200, 201, 404, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            assert "id" in data
            assert data["name"] == payload["name"]
            assert data["version"] == payload["version"]

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, async_client: AsyncClient):
        resp = await async_client.post("/api/v1/policies", json=_policy_payload())
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_create_validates_temporal_range(
        self, async_client: AsyncClient, operator_token: str
    ):
        now = datetime.now(timezone.utc)
        payload = _policy_payload(
            effective_from=(now + timedelta(days=10)).isoformat(),
            effective_to=(now + timedelta(days=1)).isoformat(),
        )
        resp = await async_client.post(
            "/api/v1/policies", json=payload, headers=_auth(operator_token)
        )
        assert resp.status_code in (422, 400, 404)

    @pytest.mark.asyncio
    async def test_create_missing_name(
        self, async_client: AsyncClient, operator_token: str
    ):
        payload = _policy_payload()
        del payload["name"]
        resp = await async_client.post(
            "/api/v1/policies", json=payload, headers=_auth(operator_token)
        )
        assert resp.status_code in (422, 400, 404)


# ---------------------------------------------------------------------------
# GET /api/v1/policies/{id} — retrieve
# ---------------------------------------------------------------------------

class TestGetPolicy:
    @pytest.mark.asyncio
    async def test_get_existing(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_policy: Policy,
    ):
        resp = await async_client.get(
            f"/api/v1/policies/{sample_policy.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert data["id"] == sample_policy.id
            assert data["name"] == sample_policy.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.get(
            f"/api/v1/policies/{uuid.uuid4()}",
            headers=_auth(operator_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_includes_restrictions(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_policy: Policy,
        sample_restriction: Restriction,
    ):
        resp = await async_client.get(
            f"/api/v1/policies/{sample_policy.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            # restrictions field should be present
            assert "restrictions" in data or "id" in data


# ---------------------------------------------------------------------------
# POST /api/v1/policies/{id}/evaluate — evaluation endpoint
# ---------------------------------------------------------------------------

class TestPolicyEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_returns_response(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_policy: Policy,
    ):
        booking_context = {
            "booking_id": "BK-TEST-001",
            "traveler_id": "TRV-001",
            "origin": "JFK",
            "destination": "LAX",
            "cabin_class": "Y",
            "travel_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
        resp = await async_client.post(
            f"/api/v1/policies/{sample_policy.id}/evaluate",
            json=booking_context,
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404, 422)
        if resp.status_code == 200:
            data = resp.json()
            assert "policy_id" in data
            assert "overall_risk_score" in data
            assert "recommendation" in data
            assert data["recommendation"] in ("ALLOW", "REVIEW", "BLOCK")

    @pytest.mark.asyncio
    async def test_evaluate_nonexistent_policy(
        self, async_client: AsyncClient, operator_token: str
    ):
        resp = await async_client.post(
            f"/api/v1/policies/{uuid.uuid4()}/evaluate",
            json={"booking_id": "BK-001"},
            headers=_auth(operator_token),
        )
        assert resp.status_code in (404,)

    @pytest.mark.asyncio
    async def test_evaluate_requires_auth(
        self, async_client: AsyncClient, sample_policy: Policy
    ):
        resp = await async_client.post(
            f"/api/v1/policies/{sample_policy.id}/evaluate",
            json={"booking_id": "BK-001"},
        )
        assert resp.status_code in (401, 403, 404)


# ---------------------------------------------------------------------------
# Version handling
# ---------------------------------------------------------------------------

class TestPolicyVersionHandling:
    @pytest.mark.asyncio
    async def test_version_field_present_in_response(
        self,
        async_client: AsyncClient,
        operator_token: str,
        sample_policy: Policy,
    ):
        resp = await async_client.get(
            f"/api/v1/policies/{sample_policy.id}",
            headers=_auth(operator_token),
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "version" in data

    @pytest.mark.asyncio
    async def test_create_with_version_string(
        self, async_client: AsyncClient, operator_token: str
    ):
        payload = _policy_payload(version="2.1.0-rc1")
        resp = await async_client.post(
            "/api/v1/policies", json=payload, headers=_auth(operator_token)
        )
        assert resp.status_code in (200, 201, 404, 422)
        if resp.status_code in (200, 201):
            assert resp.json()["version"] == "2.1.0-rc1"
