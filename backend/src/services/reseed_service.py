"""Synthetic data reseed service.

Truncates non-audit tables and regenerates a consistent, deterministic
dataset for repeatable demonstrations.

Preserved tables: users, hash_chained_audit_logs, audit_logs
Truncated tables: policies, restrictions, evidence, approval_requests,
                  conversations, messages
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.evidence import Evidence
from backend.src.models.policy import Policy
from backend.src.models.restriction import Restriction

logger = logging.getLogger(__name__)

# Deterministic seed namespace UUID — ensures IDs are stable across reseeds
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _det_uuid(name: str) -> str:
    """Generate a deterministic UUID v5 from a name string."""
    return str(uuid.uuid5(_NS, name))


# ── Synthetic dataset definition ──────────────────────────────────────────────

NOW = datetime.now(timezone.utc)


def _build_policies() -> list[dict[str, Any]]:
    return [
        {
            "id": _det_uuid("policy-001"),
            "name": "No-Smoking Policy",
            "version": "2.1",
            "description": "Strict no-smoking rule across all indoor areas and within 10m of entrances.",
            "document_url": "https://docs.example.com/policies/no-smoking-v2.1.pdf",
            "effective_from": NOW - timedelta(days=365),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=365),
            "updated_at": NOW - timedelta(days=365),
        },
        {
            "id": _det_uuid("policy-002"),
            "name": "Pet Policy",
            "version": "1.3",
            "description": "Pets allowed in designated rooms only; deposit required.",
            "document_url": "https://docs.example.com/policies/pets-v1.3.pdf",
            "effective_from": NOW - timedelta(days=180),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=180),
            "updated_at": NOW - timedelta(days=90),
        },
        {
            "id": _det_uuid("policy-003"),
            "name": "Minimum Stay Policy",
            "version": "3.0",
            "description": "Minimum 2-night stay required during peak season (Jun–Aug).",
            "document_url": "https://docs.example.com/policies/min-stay-v3.0.pdf",
            "effective_from": NOW - timedelta(days=730),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=730),
            "updated_at": NOW - timedelta(days=30),
        },
        {
            "id": _det_uuid("policy-004"),
            "name": "Age Verification Policy",
            "version": "1.0",
            "description": "Guests must be 18+ to book; ID verification required at check-in.",
            "document_url": "https://docs.example.com/policies/age-verify-v1.0.pdf",
            "effective_from": NOW - timedelta(days=500),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=500),
            "updated_at": NOW - timedelta(days=500),
        },
        {
            "id": _det_uuid("policy-005"),
            "name": "Noise Curfew Policy",
            "version": "2.0",
            "description": "Quiet hours enforced 22:00–08:00 in all residential zones.",
            "document_url": "https://docs.example.com/policies/noise-curfew-v2.0.pdf",
            "effective_from": NOW - timedelta(days=270),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=270),
            "updated_at": NOW - timedelta(days=60),
        },
        {
            "id": _det_uuid("policy-006"),
            "name": "Cancellation Policy (Legacy)",
            "version": "1.0",
            "description": "Superseded by v2.0; kept for historical reference.",
            "document_url": None,
            "effective_from": NOW - timedelta(days=1000),
            "effective_to": NOW - timedelta(days=365),
            "is_active": False,
            "created_at": NOW - timedelta(days=1000),
            "updated_at": NOW - timedelta(days=365),
        },
    ]


def _build_restrictions() -> list[dict[str, Any]]:
    return [
        {
            "id": _det_uuid("restriction-001"),
            "name": "Indoor Smoking Ban",
            "description": "No smoking permitted in any indoor area.",
            "rule_type": "prohibition",
            "parameters": {"zone": "indoor", "substance": "tobacco"},
            "risk_level": 5,
            "source_policy_id": _det_uuid("policy-001"),
            "effective_from": NOW - timedelta(days=365),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=365),
            "updated_at": NOW - timedelta(days=365),
        },
        {
            "id": _det_uuid("restriction-002"),
            "name": "Pet Deposit Requirement",
            "description": "Refundable deposit of $150 required for pet-friendly rooms.",
            "rule_type": "financial_requirement",
            "parameters": {"deposit_amount": 150, "currency": "USD", "refundable": True},
            "risk_level": 2,
            "source_policy_id": _det_uuid("policy-002"),
            "effective_from": NOW - timedelta(days=180),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=180),
            "updated_at": NOW - timedelta(days=90),
        },
        {
            "id": _det_uuid("restriction-003"),
            "name": "Peak Season Minimum Stay",
            "description": "2-night minimum stay required June through August.",
            "rule_type": "stay_requirement",
            "parameters": {"min_nights": 2, "months": [6, 7, 8]},
            "risk_level": 3,
            "source_policy_id": _det_uuid("policy-003"),
            "effective_from": NOW - timedelta(days=730),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=730),
            "updated_at": NOW - timedelta(days=30),
        },
        {
            "id": _det_uuid("restriction-004"),
            "name": "Age 18+ Booking Requirement",
            "description": "Primary guest must be at least 18 years of age.",
            "rule_type": "age_requirement",
            "parameters": {"min_age": 18, "id_required": True},
            "risk_level": 4,
            "source_policy_id": _det_uuid("policy-004"),
            "effective_from": NOW - timedelta(days=500),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=500),
            "updated_at": NOW - timedelta(days=500),
        },
        {
            "id": _det_uuid("restriction-005"),
            "name": "Late Night Noise Restriction",
            "description": "No loud music or gatherings after 22:00.",
            "rule_type": "time_restriction",
            "parameters": {"quiet_start": "22:00", "quiet_end": "08:00"},
            "risk_level": 3,
            "source_policy_id": _det_uuid("policy-005"),
            "effective_from": NOW - timedelta(days=270),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=270),
            "updated_at": NOW - timedelta(days=60),
        },
        {
            "id": _det_uuid("restriction-006"),
            "name": "No Unregistered Guests Overnight",
            "description": "Only registered guests may stay overnight.",
            "rule_type": "occupancy_rule",
            "parameters": {"registered_only": True, "overnight": True},
            "risk_level": 4,
            "source_policy_id": None,
            "effective_from": NOW - timedelta(days=400),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=400),
            "updated_at": NOW - timedelta(days=400),
        },
        {
            "id": _det_uuid("restriction-007"),
            "name": "No Commercial Photography",
            "description": "Commercial photography or filming requires prior written approval.",
            "rule_type": "activity_restriction",
            "parameters": {"activity": "commercial_photography", "approval_required": True},
            "risk_level": 2,
            "source_policy_id": None,
            "effective_from": NOW - timedelta(days=200),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=200),
            "updated_at": NOW - timedelta(days=200),
        },
        {
            "id": _det_uuid("restriction-008"),
            "name": "Parking Permit Required",
            "description": "Vehicles must display a valid parking permit.",
            "rule_type": "permit_requirement",
            "parameters": {"permit_type": "parking", "display_required": True},
            "risk_level": 1,
            "source_policy_id": None,
            "effective_from": NOW - timedelta(days=150),
            "effective_to": None,
            "is_active": True,
            "created_at": NOW - timedelta(days=150),
            "updated_at": NOW - timedelta(days=150),
        },
    ]


def _build_evidence(restrictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build evidence records linked to the first 4 restrictions."""
    items = []
    for i, restr in enumerate(restrictions[:4]):
        items.append({
            "id": _det_uuid(f"evidence-{i+1:03d}-a"),
            "restriction_id": restr["id"],
            "source_table": "incident_reports",
            "source_record_id": _det_uuid(f"incident-{i+1:03d}"),
            "source_field": "violation_type",
            "evidence_value": f"Violation recorded for restriction {restr['name']}",
            "confidence_score": round(0.75 + i * 0.05, 2),
            "collected_at": NOW - timedelta(days=30 + i * 10),
            "is_active": True,
            "created_at": NOW - timedelta(days=30 + i * 10),
            "updated_at": NOW - timedelta(days=30 + i * 10),
        })
        items.append({
            "id": _det_uuid(f"evidence-{i+1:03d}-b"),
            "restriction_id": restr["id"],
            "source_table": "booking_records",
            "source_record_id": _det_uuid(f"booking-{i+1:03d}"),
            "source_field": "compliance_flag",
            "evidence_value": "non_compliant",
            "confidence_score": round(0.80 + i * 0.03, 2),
            "collected_at": NOW - timedelta(days=20 + i * 7),
            "is_active": True,
            "created_at": NOW - timedelta(days=20 + i * 7),
            "updated_at": NOW - timedelta(days=20 + i * 7),
        })
    return items


def _build_approval_requests(restrictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses = ["pending", "pending", "escalated", "approved", "rejected", "pending"]
    priorities = ["high", "medium", "high", "low", "medium", "high"]
    queue_types = [
        "high_risk", "low_confidence", "high_risk",
        "low_confidence", "high_risk", "low_confidence",
    ]
    items = []
    for i in range(6):
        restr = restrictions[i % len(restrictions)]
        status = statuses[i]
        decided_at = (NOW - timedelta(days=5 + i)) if status in ("approved", "rejected") else None
        items.append({
            "id": _det_uuid(f"approval-{i+1:03d}"),
            "restriction_query_id": restr["id"],
            "risk_score": round(0.6 + i * 0.06, 2),
            "confidence_score": round(0.55 + i * 0.07, 2),
            "queue_type": queue_types[i],
            "priority": priorities[i],
            "status": status,
            "assigned_to": None,
            "decision_rationale": (
                f"Auto-generated rationale for approval request {i+1}"
                if status in ("approved", "rejected") else None
            ),
            "decided_at": decided_at,
            "context_data": json.dumps({"demo": True, "index": i + 1}),
            "is_active": True,
            "created_at": NOW - timedelta(days=20 + i * 3),
            "updated_at": NOW - timedelta(days=5 + i),
        })
    return items


# ── Reseed service ────────────────────────────────────────────────────────────

class ReseedService:
    """Truncate non-audit tables and regenerate synthetic demo data."""

    # Tables to truncate (in dependency order — children first)
    _TRUNCATE_ORDER = [
        "messages",
        "conversations",
        "approval_requests",
        "evidence",
        "restrictions",
        "policies",
    ]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def reseed(self) -> dict[str, Any]:
        """Truncate and regenerate all synthetic data.

        Returns a summary dict with record counts and a validation checksum.
        """
        logger.info("Starting synthetic data reseed")

        # 1. Truncate in dependency order
        for table in self._TRUNCATE_ORDER:
            await self.db.execute(text(f"DELETE FROM {table}"))  # noqa: S608
            logger.debug("Truncated table: %s", table)

        await self.db.flush()

        # 2. Regenerate
        policies = _build_policies()
        restrictions = _build_restrictions()
        evidence_items = _build_evidence(restrictions)
        approval_requests = _build_approval_requests(restrictions)

        # Insert policies
        for p in policies:
            obj = Policy(
                id=p["id"],
                name=p["name"],
                version=p["version"],
                description=p["description"],
                document_url=p["document_url"],
                effective_from=p["effective_from"],
                effective_to=p["effective_to"],
                is_active=p["is_active"],
            )
            self.db.add(obj)

        await self.db.flush()

        # Insert restrictions
        for r in restrictions:
            obj = Restriction(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                rule_type=r["rule_type"],
                parameters=r["parameters"],
                risk_level=r["risk_level"],
                source_policy_id=r["source_policy_id"],
                effective_from=r["effective_from"],
                effective_to=r["effective_to"],
                is_active=r["is_active"],
            )
            self.db.add(obj)

        await self.db.flush()

        # Insert evidence
        for e in evidence_items:
            obj = Evidence(
                id=e["id"],
                restriction_id=e["restriction_id"],
                source_table=e["source_table"],
                source_record_id=e["source_record_id"],
                source_field=e["source_field"],
                evidence_value=e["evidence_value"],
                confidence_score=e["confidence_score"],
                collected_at=e["collected_at"],
            )
            self.db.add(obj)

        await self.db.flush()

        # Insert approval requests
        for a in approval_requests:
            obj = ApprovalRequest(
                id=a["id"],
                restriction_query_id=a["restriction_query_id"],
                risk_score=a["risk_score"],
                confidence_score=a["confidence_score"],
                queue_type=a["queue_type"],
                priority=a["priority"],
                status=a["status"],
                assigned_to=a["assigned_to"],
                decision_rationale=a["decision_rationale"],
                decided_at=a["decided_at"],
                context_data=a["context_data"],
                is_active=a["is_active"],
            )
            self.db.add(obj)

        await self.db.flush()

        # 3. Compute validation checksum
        all_ids = (
            [p["id"] for p in policies]
            + [r["id"] for r in restrictions]
            + [e["id"] for e in evidence_items]
            + [a["id"] for a in approval_requests]
        )
        checksum = hashlib.sha256("|".join(sorted(all_ids)).encode()).hexdigest()

        summary = {
            "policies": len(policies),
            "restrictions": len(restrictions),
            "evidence_items": len(evidence_items),
            "approval_requests": len(approval_requests),
            "total_records": len(all_ids),
            "validation_checksum": checksum,
            "reseeded_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Reseed complete: %s", summary)
        return summary
