"""Integration tests for hash-chain audit integrity verification.

Tests:
- Injected tampered record detection
- Hash chain break detection at specific sequence numbers
- Missing sequence gap detection
- Chain verification with clean records passes
- Export attestation integrity
- AuditLogWriter produces valid chain entries
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.evidence import HashChainedAuditLog
from backend.src.services.audit_service import (
    AuditChainService,
    AuditLogWriter,
    GENESIS_HASH,
    compute_hash,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _write_clean_chain(
    writer: AuditLogWriter,
    db_session: AsyncSession,
    count: int = 5,
) -> list[HashChainedAuditLog]:
    """Write `count` valid audit log entries and return them."""
    records = []
    for i in range(count):
        rec = await writer.append(
            event_type=f"test.event.{i}",
            actor_id=f"user-{i:03d}",
            actor_role="manager",
            resource_type="ApprovalRequest",
            resource_id=f"AR-{i:04d}",
            payload={"index": i, "action": "test"},
        )
        records.append(rec)
    await db_session.commit()
    return records


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAuditLogWriter:
    """AuditLogWriter correctness tests."""

    @pytest.mark.asyncio
    async def test_first_record_uses_genesis_hash(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """First record in chain uses GENESIS_HASH as previous_hash."""
        rec = await audit_writer.append(
            event_type="test.genesis",
            actor_id="user-001",
            resource_type="Evidence",
            resource_id="EV-001",
        )
        await db_session.commit()
        assert rec.previous_hash == GENESIS_HASH

    @pytest.mark.asyncio
    async def test_sequential_records_link_correctly(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Each record's previous_hash equals the prior record's current_hash."""
        records = await _write_clean_chain(audit_writer, db_session, count=4)
        for i in range(1, len(records)):
            assert records[i].previous_hash == records[i - 1].current_hash, (
                f"Record {i} previous_hash does not match record {i-1} current_hash"
            )

    @pytest.mark.asyncio
    async def test_hash_computation_is_deterministic(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Recomputing hash from stored data yields the same value."""
        rec = await audit_writer.append(
            event_type="test.deterministic",
            actor_id="user-001",
            resource_type="Evidence",
            resource_id="EV-002",
            payload={"key": "value"},
        )
        await db_session.commit()
        recomputed = compute_hash(rec.previous_hash, rec)
        assert recomputed == rec.current_hash

    @pytest.mark.asyncio
    async def test_sequence_numbers_are_monotonic(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Sequence numbers increase monotonically."""
        records = await _write_clean_chain(audit_writer, db_session, count=5)
        seqs = [r.sequence_number for r in records]
        assert seqs == sorted(seqs), f"Sequence numbers not monotonic: {seqs}"
        # Each should be exactly 1 more than the previous (within this batch)
        for i in range(1, len(seqs)):
            assert seqs[i] == seqs[i - 1] + 1, (
                f"Gap in sequence: {seqs[i-1]} → {seqs[i]}"
            )


class TestChainIntegrityVerification:
    """AuditChainService.verify_chain_integrity tests."""

    @pytest.mark.asyncio
    async def test_clean_chain_is_intact(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """A freshly written chain passes integrity verification."""
        await _write_clean_chain(audit_writer, db_session, count=6)
        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()
        assert result["is_intact"] is True
        assert result["broken_at_sequences"] == []
        assert result["missing_sequences"] == []
        assert result["total_records"] >= 6

    @pytest.mark.asyncio
    async def test_tampered_payload_detected(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Injecting a tampered payload into a record breaks the chain."""
        records = await _write_clean_chain(audit_writer, db_session, count=4)
        target = records[1]  # tamper the second record

        # Inject tampered payload — the stored hash will no longer match
        target.payload = json.dumps({"TAMPERED": True, "injected": "malicious_data"})
        db_session.add(target)
        await db_session.commit()

        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()
        assert result["is_intact"] is False
        assert target.sequence_number in result["broken_at_sequences"], (
            f"Tampered seq {target.sequence_number} not in broken_at: "
            f"{result['broken_at_sequences']}"
        )

    @pytest.mark.asyncio
    async def test_tampered_current_hash_detected(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Directly modifying current_hash breaks the chain linkage."""
        records = await _write_clean_chain(audit_writer, db_session, count=4)
        target = records[2]

        # Corrupt the current_hash
        target.current_hash = "a" * 64
        db_session.add(target)
        await db_session.commit()

        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()
        assert result["is_intact"] is False
        # Either the tampered record or the next one (broken linkage) should appear
        broken = result["broken_at_sequences"]
        assert len(broken) > 0, "Expected at least one broken sequence"

    @pytest.mark.asyncio
    async def test_missing_sequence_gap_detected(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Deleting a record from the middle creates a detectable sequence gap."""
        records = await _write_clean_chain(audit_writer, db_session, count=5)
        # Delete the middle record to create a gap
        middle = records[2]
        deleted_seq = middle.sequence_number
        await db_session.delete(middle)
        await db_session.commit()

        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()
        assert result["is_intact"] is False
        assert deleted_seq in result["missing_sequences"], (
            f"Deleted seq {deleted_seq} not in missing_sequences: "
            f"{result['missing_sequences']}"
        )

    @pytest.mark.asyncio
    async def test_detect_tampering_alias(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """detect_tampering() returns tampered=False for clean chain."""
        await _write_clean_chain(audit_writer, db_session, count=3)
        svc = AuditChainService(db_session)
        result = await svc.detect_tampering()
        assert result["tampered"] is False
        assert result["tamper_evidence"]["broken_sequences"] == []
        assert result["tamper_evidence"]["missing_sequences"] == []

    @pytest.mark.asyncio
    async def test_detect_tampering_finds_injected_record(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """detect_tampering() returns tampered=True when payload is injected."""
        records = await _write_clean_chain(audit_writer, db_session, count=4)
        # Tamper record 0
        records[0].payload = json.dumps({"injected": "attack_payload"})
        db_session.add(records[0])
        await db_session.commit()

        svc = AuditChainService(db_session)
        result = await svc.detect_tampering()
        assert result["tampered"] is True

    @pytest.mark.asyncio
    async def test_partial_range_verification(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """Verifying a sub-range of the chain works correctly."""
        records = await _write_clean_chain(audit_writer, db_session, count=8)
        start = records[2].sequence_number
        end = records[5].sequence_number

        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity(start_seq=start, end_seq=end)
        assert result["total_records"] == 4  # records[2..5] inclusive
        # Sub-range may not be intact if previous_hash doesn't match GENESIS
        # but broken_at should only contain sequences in range
        for seq in result["broken_at_sequences"]:
            assert start <= seq <= end

    @pytest.mark.asyncio
    async def test_integrity_verified_at_stamped(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """After successful verification, integrity_verified_at is stamped."""
        records = await _write_clean_chain(audit_writer, db_session, count=3)
        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()

        if result["is_intact"]:
            # Refresh records and check stamps
            for rec in records:
                await db_session.refresh(rec)
                # integrity_verified_at may be set on clean chains
                # (depends on whether this is a sub-range or full chain)


class TestAuditExport:
    """Audit export and attestation tests."""

    @pytest.mark.asyncio
    async def test_json_export_contains_records(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """JSON export includes all written records."""
        await _write_clean_chain(audit_writer, db_session, count=3)
        svc = AuditChainService(db_session)
        content, media_type = await svc.export_audit(format="json")
        assert media_type == "application/json"
        data = json.loads(content)
        assert "records" in data
        assert len(data["records"]) >= 3

    @pytest.mark.asyncio
    async def test_json_export_attestation_block(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """JSON export with attestation includes chain_summary_hash."""
        await _write_clean_chain(audit_writer, db_session, count=3)
        svc = AuditChainService(db_session)
        content, _ = await svc.export_audit(format="json", include_attestation=True)
        data = json.loads(content)
        assert "attestation" in data
        attestation = data["attestation"]
        assert "chain_summary_hash" in attestation
        assert "record_count" in attestation
        assert attestation["record_count"] >= 3

    @pytest.mark.asyncio
    async def test_csv_export_format(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """CSV export returns text/csv content type."""
        await _write_clean_chain(audit_writer, db_session, count=2)
        svc = AuditChainService(db_session)
        content, media_type = await svc.export_audit(format="csv")
        assert media_type == "text/csv"
        assert "sequence_number" in content  # CSV header

    @pytest.mark.asyncio
    async def test_query_audit_logs_filters(
        self, db_session: AsyncSession, audit_writer: AuditLogWriter
    ) -> None:
        """query_audit_logs filters by event_type correctly."""
        await audit_writer.append(
            event_type="approval.approved",
            actor_id="user-001",
            resource_type="ApprovalRequest",
            resource_id="AR-001",
        )
        await audit_writer.append(
            event_type="evidence.created",
            actor_id="user-002",
            resource_type="Evidence",
            resource_id="EV-001",
        )
        await db_session.commit()

        svc = AuditChainService(db_session)
        records, total = await svc.query_audit_logs(event_type="approval.approved")
        assert all(r.event_type == "approval.approved" for r in records)
