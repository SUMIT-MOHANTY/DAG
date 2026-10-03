"""Audit integrity service — hash-chain verification, tampering detection, and export.

This module provides:
- ``AuditChainService``: verify_chain_integrity(), detect_tampering(), export_audit()
- ``AuditLogWriter``: append-only writer that maintains the SHA-256 hash chain
- Helper to compute canonical record hashes

Hash-chain protocol
-------------------
For record N:
    payload_str  = JSON-serialised canonical payload (sorted keys)
    current_hash = SHA-256( previous_hash_N + payload_str )

The first record uses the sentinel ``GENESIS`` as its previous_hash.
Any gap in sequence_number or mismatch between stored current_hash and the
recomputed value indicates tampering.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.evidence import HashChainedAuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64  # sentinel for the first record in the chain


# ── Hash computation ──────────────────────────────────────────────────────────

def _canonical_payload(record: HashChainedAuditLog) -> str:
    """Return a deterministic JSON string of the record's event payload."""
    data: dict[str, Any] = {
        "sequence_number": record.sequence_number,
        "event_type": record.event_type,
        "actor_id": record.actor_id,
        "actor_role": record.actor_role,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "payload": record.payload,
        "ip_address": record.ip_address,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=True)


def compute_hash(previous_hash: str, record: HashChainedAuditLog) -> str:
    """Compute SHA-256( previous_hash + canonical_payload )."""
    payload_str = _canonical_payload(record)
    raw = (previous_hash + payload_str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ── Append-only writer ────────────────────────────────────────────────────────

class AuditLogWriter:
    """Append-only writer that maintains the SHA-256 hash chain.

    Usage::

        writer = AuditLogWriter(db)
        await writer.append(
            event_type="restriction.created",
            actor_id=current_user.id,
            actor_role=current_user.role,
            resource_type="Restriction",
            resource_id=restriction.id,
            payload={"name": restriction.name},
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _next_sequence(self) -> int:
        """Return the next monotonic sequence number."""
        result = await self.db.execute(
            select(func.max(HashChainedAuditLog.sequence_number))
        )
        max_seq: Optional[int] = result.scalar_one_or_none()
        return (max_seq or 0) + 1

    async def _last_hash(self) -> str:
        """Return the current_hash of the most recent record, or GENESIS."""
        result = await self.db.execute(
            select(HashChainedAuditLog.current_hash)
            .order_by(HashChainedAuditLog.sequence_number.desc())
            .limit(1)
        )
        last: Optional[str] = result.scalar_one_or_none()
        return last if last is not None else GENESIS_HASH

    async def append(
        self,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> HashChainedAuditLog:
        """Create and persist a new hash-chained audit log entry."""
        seq = await self._next_sequence()
        prev_hash = await self._last_hash()
        now = datetime.now(timezone.utc)

        record = HashChainedAuditLog(
            id=str(uuid.uuid4()),
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=json.dumps(payload, sort_keys=True) if payload else None,
            ip_address=ip_address,
            sequence_number=seq,
            previous_hash=prev_hash,
            current_hash="",  # placeholder — computed below
            created_at=now,
        )
        # Compute hash after all fields are set
        record.current_hash = compute_hash(prev_hash, record)

        self.db.add(record)
        await self.db.flush()  # get DB-assigned values without committing
        logger.debug(
            "Audit entry appended: seq=%d event=%s hash=%s",
            seq, event_type, record.current_hash[:12],
        )
        return record


# ── Chain verification service ────────────────────────────────────────────────

class AuditChainService:
    """Verify hash-chain integrity and export audit records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Integrity verification ────────────────────────────────────────────────

    async def verify_chain_integrity(
        self,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
    ) -> dict[str, Any]:
        """Recompute every hash in the chain and report any breaks.

        Returns a summary dict with:
        - ``is_intact``: True if no tampering detected
        - ``total_records``: number of records examined
        - ``broken_at``: list of sequence numbers where the chain breaks
        - ``gaps``: list of missing sequence numbers
        - ``verified_at``: ISO timestamp of this verification run
        """
        query = select(HashChainedAuditLog).order_by(
            HashChainedAuditLog.sequence_number.asc()
        )
        if start_seq is not None:
            query = query.where(HashChainedAuditLog.sequence_number >= start_seq)
        if end_seq is not None:
            query = query.where(HashChainedAuditLog.sequence_number <= end_seq)

        result = await self.db.execute(query)
        records: list[HashChainedAuditLog] = list(result.scalars().all())

        broken_at: list[int] = []
        gaps: list[int] = []
        expected_prev = GENESIS_HASH
        expected_seq: Optional[int] = None

        for rec in records:
            # Check for sequence gaps
            if expected_seq is not None and rec.sequence_number != expected_seq:
                for missing in range(expected_seq, rec.sequence_number):
                    gaps.append(missing)

            # Verify previous_hash linkage
            if rec.previous_hash != expected_prev:
                broken_at.append(rec.sequence_number)
                logger.warning(
                    "Hash chain break at seq=%d: expected_prev=%s stored_prev=%s",
                    rec.sequence_number, expected_prev[:12], rec.previous_hash[:12],
                )

            # Recompute current_hash
            recomputed = compute_hash(rec.previous_hash, rec)
            if recomputed != rec.current_hash:
                if rec.sequence_number not in broken_at:
                    broken_at.append(rec.sequence_number)
                logger.warning(
                    "Hash mismatch at seq=%d: stored=%s recomputed=%s",
                    rec.sequence_number, rec.current_hash[:12], recomputed[:12],
                )

            expected_prev = rec.current_hash
            expected_seq = rec.sequence_number + 1

        # Stamp verification time on all verified records (batch update)
        if records and not broken_at:
            now = datetime.now(timezone.utc)
            for rec in records:
                rec.integrity_verified_at = now
            await self.db.flush()

        return {
            "is_intact": len(broken_at) == 0 and len(gaps) == 0,
            "total_records": len(records),
            "broken_at_sequences": sorted(broken_at),
            "missing_sequences": sorted(gaps),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    async def detect_tampering(
        self,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
    ) -> dict[str, Any]:
        """Alias for verify_chain_integrity with a tamper-focused response shape."""
        result = await self.verify_chain_integrity(start_seq=start_seq, end_seq=end_seq)
        return {
            "tampered": not result["is_intact"],
            "tamper_evidence": {
                "broken_sequences": result["broken_at_sequences"],
                "missing_sequences": result["missing_sequences"],
            },
            "records_examined": result["total_records"],
            "verified_at": result["verified_at"],
        }

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def query_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        integrity_status: Optional[str] = None,  # "verified" | "unverified" | "all"
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[HashChainedAuditLog], int]:
        """Return filtered audit log records and total count."""
        query = select(HashChainedAuditLog)
        count_query = select(func.count()).select_from(HashChainedAuditLog)

        filters = []
        if start_time:
            filters.append(HashChainedAuditLog.created_at >= start_time)
        if end_time:
            filters.append(HashChainedAuditLog.created_at <= end_time)
        if event_type:
            filters.append(HashChainedAuditLog.event_type == event_type)
        if actor_id:
            filters.append(HashChainedAuditLog.actor_id == actor_id)
        if resource_type:
            filters.append(HashChainedAuditLog.resource_type == resource_type)
        if resource_id:
            filters.append(HashChainedAuditLog.resource_id == resource_id)
        if integrity_status == "verified":
            filters.append(HashChainedAuditLog.integrity_verified_at.isnot(None))
        elif integrity_status == "unverified":
            filters.append(HashChainedAuditLog.integrity_verified_at.is_(None))

        if filters:
            from sqlalchemy import and_
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total_result = await self.db.execute(count_query)
        total: int = total_result.scalar_one()

        query = query.order_by(HashChainedAuditLog.sequence_number.asc()).offset(skip).limit(limit)
        records_result = await self.db.execute(query)
        records = list(records_result.scalars().all())

        return records, total

    # ── Export ────────────────────────────────────────────────────────────────

    async def export_audit(
        self,
        format: str = "json",  # "json" | "csv"
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        include_attestation: bool = True,
    ) -> tuple[str, str]:
        """Export filtered audit trail with optional integrity attestation.

        Returns (content: str, media_type: str).
        """
        records, _ = await self.query_audit_logs(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
            resource_type=resource_type,
            limit=10_000,
        )

        rows = [
            {
                "sequence_number": r.sequence_number,
                "id": r.id,
                "event_type": r.event_type,
                "actor_id": r.actor_id,
                "actor_role": r.actor_role,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "payload": r.payload,
                "ip_address": r.ip_address,
                "previous_hash": r.previous_hash,
                "current_hash": r.current_hash,
                "integrity_verified_at": (
                    r.integrity_verified_at.isoformat() if r.integrity_verified_at else None
                ),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

        attestation: Optional[dict[str, Any]] = None
        if include_attestation and records:
            # Compute a summary hash over all current_hashes for attestation
            chain_summary = hashlib.sha256(
                "|".join(r.current_hash for r in records).encode()
            ).hexdigest()
            attestation = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "record_count": len(records),
                "first_sequence": records[0].sequence_number,
                "last_sequence": records[-1].sequence_number,
                "chain_summary_hash": chain_summary,
                "integrity_attestation": "SHA-256 hash chain — see chain_summary_hash",
            }

        if format == "csv":
            buf = io.StringIO()
            if rows:
                writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            if attestation:
                buf.write("\n# ATTESTATION\n")
                for k, v in attestation.items():
                    buf.write(f"# {k}: {v}\n")
            return buf.getvalue(), "text/csv"
        else:
            export_doc: dict[str, Any] = {"records": rows}
            if attestation:
                export_doc["attestation"] = attestation
            return json.dumps(export_doc, indent=2), "application/json"
