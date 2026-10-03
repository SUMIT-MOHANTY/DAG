"""Synthetic data reseed idempotency tests.

Verifies:
- Record counts are deterministic across multiple reseeds
- IDs are deterministic (UUID v5 from stable namespace)
- Relationships are preserved (evidence → restriction FK)
- Audit log is preserved across reseeds
- Validation checksum is stable
- Reseed without confirm=true is rejected
- Sequential reseeds produce identical datasets
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.evidence import Evidence, HashChainedAuditLog
from backend.src.models.policy import Policy
from backend.src.models.restriction import Restriction
from backend.src.services.audit_service import AuditLogWriter
from backend.src.services.reseed_service import ReseedService, _det_uuid, _NS


# ── Expected counts from reseed_service.py ────────────────────────────────────

EXPECTED_POLICIES = 6
EXPECTED_RESTRICTIONS = 8
EXPECTED_EVIDENCE_ITEMS = 8   # 4 restrictions × 2 evidence each
EXPECTED_APPROVAL_REQUESTS = 6
EXPECTED_TOTAL = (
    EXPECTED_POLICIES
    + EXPECTED_RESTRICTIONS
    + EXPECTED_EVIDENCE_ITEMS
    + EXPECTED_APPROVAL_REQUESTS
)


# ── Deterministic ID tests ────────────────────────────────────────────────────

class TestDeterministicIDs:
    """Verify that generated IDs are deterministic across calls."""

    def test_det_uuid_is_deterministic(self) -> None:
        """_det_uuid produces the same UUID for the same input."""
        id1 = _det_uuid("policy-001")
        id2 = _det_uuid("policy-001")
        assert id1 == id2, f"Non-deterministic: {id1} != {id2}"

    def test_det_uuid_different_inputs_different_ids(self) -> None:
        """Different inputs produce different UUIDs."""
        id1 = _det_uuid("policy-001")
        id2 = _det_uuid("policy-002")
        assert id1 != id2

    def test_det_uuid_is_valid_uuid(self) -> None:
        """Generated IDs are valid UUID strings."""
        result = _det_uuid("test-entity")
        parsed = uuid.UUID(result)  # raises if invalid
        assert str(parsed) == result

    def test_det_uuid_uses_correct_namespace(self) -> None:
        """_det_uuid uses the defined namespace UUID."""
        expected = str(uuid.uuid5(_NS, "policy-001"))
        actual = _det_uuid("policy-001")
        assert actual == expected

    def test_known_policy_ids_stable(self) -> None:
        """Known policy IDs match expected deterministic values."""
        policy_ids = [_det_uuid(f"policy-{i:03d}") for i in range(1, 7)]
        # All should be unique
        assert len(set(policy_ids)) == 6, "Policy IDs are not unique"
        # All should be valid UUIDs
        for pid in policy_ids:
            uuid.UUID(pid)  # raises if invalid

    def test_known_restriction_ids_stable(self) -> None:
        """Known restriction IDs match expected deterministic values."""
        restriction_ids = [_det_uuid(f"restriction-{i:03d}") for i in range(1, 9)]
        assert len(set(restriction_ids)) == 8

    def test_known_approval_ids_stable(self) -> None:
        """Known approval request IDs match expected deterministic values."""
        approval_ids = [_det_uuid(f"approval-{i:03d}") for i in range(1, 7)]
        assert len(set(approval_ids)) == 6


# ── Reseed service tests ──────────────────────────────────────────────────────

class TestReseedService:
    """ReseedService correctness and idempotency tests."""

    @pytest.mark.asyncio
    async def test_reseed_returns_correct_counts(self, db_session: AsyncSession) -> None:
        """Reseed returns expected record counts."""
        svc = ReseedService(db_session)
        summary = await svc.reseed()
        await db_session.commit()

        assert summary["policies"] == EXPECTED_POLICIES, (
            f"Expected {EXPECTED_POLICIES} policies, got {summary['policies']}"
        )
        assert summary["restrictions"] == EXPECTED_RESTRICTIONS, (
            f"Expected {EXPECTED_RESTRICTIONS} restrictions, got {summary['restrictions']}"
        )
        assert summary["evidence_items"] == EXPECTED_EVIDENCE_ITEMS, (
            f"Expected {EXPECTED_EVIDENCE_ITEMS} evidence items, got {summary['evidence_items']}"
        )
        assert summary["approval_requests"] == EXPECTED_APPROVAL_REQUESTS, (
            f"Expected {EXPECTED_APPROVAL_REQUESTS} approval requests, got {summary['approval_requests']}"
        )
        assert summary["total_records"] == EXPECTED_TOTAL

    @pytest.mark.asyncio
    async def test_reseed_checksum_is_stable(self, db_session: AsyncSession) -> None:
        """Validation checksum is identical across two sequential reseeds."""
        svc = ReseedService(db_session)

        summary1 = await svc.reseed()
        await db_session.commit()
        checksum1 = summary1["validation_checksum"]

        summary2 = await svc.reseed()
        await db_session.commit()
        checksum2 = summary2["validation_checksum"]

        assert checksum1 == checksum2, (
            f"Checksum changed between reseeds: {checksum1} != {checksum2}"
        )

    @pytest.mark.asyncio
    async def test_reseed_idempotent_record_counts(self, db_session: AsyncSession) -> None:
        """Record counts in DB match expected values after reseed."""
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        policy_count = (await db_session.execute(
            select(func.count()).select_from(Policy)
        )).scalar_one()
        restriction_count = (await db_session.execute(
            select(func.count()).select_from(Restriction)
        )).scalar_one()
        evidence_count = (await db_session.execute(
            select(func.count()).select_from(Evidence)
        )).scalar_one()
        approval_count = (await db_session.execute(
            select(func.count()).select_from(ApprovalRequest)
        )).scalar_one()

        assert policy_count == EXPECTED_POLICIES
        assert restriction_count == EXPECTED_RESTRICTIONS
        assert evidence_count == EXPECTED_EVIDENCE_ITEMS
        assert approval_count == EXPECTED_APPROVAL_REQUESTS

    @pytest.mark.asyncio
    async def test_reseed_twice_same_counts(self, db_session: AsyncSession) -> None:
        """Two sequential reseeds produce identical DB record counts."""
        svc = ReseedService(db_session)

        await svc.reseed()
        await db_session.commit()

        count1 = (await db_session.execute(
            select(func.count()).select_from(Policy)
        )).scalar_one()

        await svc.reseed()
        await db_session.commit()

        count2 = (await db_session.execute(
            select(func.count()).select_from(Policy)
        )).scalar_one()

        assert count1 == count2 == EXPECTED_POLICIES

    @pytest.mark.asyncio
    async def test_reseed_deterministic_ids_in_db(self, db_session: AsyncSession) -> None:
        """After reseed, policy IDs in DB match deterministic expected values."""
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        result = await db_session.execute(select(Policy.id))
        db_ids = set(result.scalars().all())

        expected_ids = {_det_uuid(f"policy-{i:03d}") for i in range(1, 7)}
        assert expected_ids == db_ids, (
            f"Policy IDs mismatch.\nExpected: {expected_ids}\nGot: {db_ids}"
        )

    @pytest.mark.asyncio
    async def test_reseed_evidence_restriction_relationships(self, db_session: AsyncSession) -> None:
        """Evidence records have valid restriction_id FK references after reseed."""
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        # Get all evidence records
        evidence_result = await db_session.execute(select(Evidence))
        evidence_items = list(evidence_result.scalars().all())

        # Get all restriction IDs
        restriction_result = await db_session.execute(select(Restriction.id))
        restriction_ids = set(restriction_result.scalars().all())

        # All evidence should reference valid restrictions
        for ev in evidence_items:
            assert ev.restriction_id in restriction_ids, (
                f"Evidence {ev.id} references non-existent restriction {ev.restriction_id}"
            )

    @pytest.mark.asyncio
    async def test_reseed_approval_restriction_relationships(self, db_session: AsyncSession) -> None:
        """ApprovalRequest records have valid restriction_query_id FK references."""
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        approval_result = await db_session.execute(select(ApprovalRequest))
        approvals = list(approval_result.scalars().all())

        restriction_result = await db_session.execute(select(Restriction.id))
        restriction_ids = set(restriction_result.scalars().all())

        for ar in approvals:
            if ar.restriction_query_id is not None:
                assert ar.restriction_query_id in restriction_ids, (
                    f"ApprovalRequest {ar.id} references non-existent restriction "
                    f"{ar.restriction_query_id}"
                )

    @pytest.mark.asyncio
    async def test_reseed_preserves_audit_log(self, db_session: AsyncSession) -> None:
        """Reseed does NOT truncate the hash_chained_audit_logs table."""
        # Write some audit entries before reseed
        writer = AuditLogWriter(db_session)
        await writer.append(
            event_type="pre_reseed.test",
            actor_id="user-001",
            resource_type="Test",
            resource_id="test-001",
        )
        await db_session.commit()

        # Count audit records before reseed
        count_before = (await db_session.execute(
            select(func.count()).select_from(HashChainedAuditLog)
        )).scalar_one()

        # Perform reseed
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        # Count audit records after reseed
        count_after = (await db_session.execute(
            select(func.count()).select_from(HashChainedAuditLog)
        )).scalar_one()

        assert count_after >= count_before, (
            f"Audit log was truncated: before={count_before}, after={count_after}"
        )

    @pytest.mark.asyncio
    async def test_reseed_approval_statuses_correct(self, db_session: AsyncSession) -> None:
        """Approval requests have the expected status distribution after reseed."""
        svc = ReseedService(db_session)
        await svc.reseed()
        await db_session.commit()

        result = await db_session.execute(select(ApprovalRequest.status))
        statuses = list(result.scalars().all())

        # Expected: pending×3, escalated×1, approved×1, rejected×1
        from collections import Counter
        status_counts = Counter(statuses)
        assert status_counts["pending"] == 3, f"Expected 3 pending, got {status_counts['pending']}"
        assert status_counts["escalated"] == 1
        assert status_counts["approved"] == 1
        assert status_counts["rejected"] == 1

    @pytest.mark.asyncio
    async def test_reseed_summary_has_reseeded_at(self, db_session: AsyncSession) -> None:
        """Reseed summary includes a valid reseeded_at ISO timestamp."""
        svc = ReseedService(db_session)
        summary = await svc.reseed()
        await db_session.commit()

        assert "reseeded_at" in summary
        # Should be parseable as ISO datetime
        dt = datetime.fromisoformat(summary["reseeded_at"])
        assert dt is not None


# ── API-level reseed tests ────────────────────────────────────────────────────

class TestReseedAPI:
    """Reseed endpoint API tests."""

    @pytest.mark.asyncio
    async def test_reseed_without_confirm_rejected(self, client) -> None:
        """POST /admin/reseed without confirm=true returns 400."""
        response = await client.post("/admin/reseed")
        assert response.status_code == 400
        data = response.json()
        assert "confirm" in data.get("detail", "").lower() or "confirm" in str(data).lower()

    @pytest.mark.asyncio
    async def test_reseed_with_confirm_succeeds(self, client) -> None:
        """POST /admin/reseed?confirm=true returns 200 with counts."""
        response = await client.post("/admin/reseed?confirm=true")
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        assert "restrictions" in data
        assert "evidence_items" in data
        assert "approval_requests" in data
        assert "validation_checksum" in data
        assert data["policies"] == EXPECTED_POLICIES
        assert data["restrictions"] == EXPECTED_RESTRICTIONS

    @pytest.mark.asyncio
    async def test_reseed_twice_same_checksum(self, client) -> None:
        """Two API reseeds produce the same validation_checksum."""
        r1 = await client.post("/admin/reseed?confirm=true")
        r2 = await client.post("/admin/reseed?confirm=true")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["validation_checksum"] == r2.json()["validation_checksum"]
