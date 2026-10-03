"""Idempotent synthetic data seed script.

Usage:
    python scripts/seed.py
    python scripts/seed.py --force   # truncate existing data before seeding

This script is safe to run multiple times.  Without ``--force`` it skips
seeding if data already exists.  With ``--force`` it truncates non-audit
tables and regenerates the full synthetic dataset.

Synthetic dataset:
  - 6 policies
  - 8 restrictions
  - 8 evidence items (2 per first-4 restrictions)
  - 6 approval requests
  - 1 admin user  (admin@example.com / admin-password)
  - 1 operator user (operator@example.com / operator-password)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the workspace root is on sys.path so backend imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed")

# ── Database URL ──────────────────────────────────────────────────────────────
import os
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./restriction_intelligence.db",
)

# ── Deterministic UUID namespace ──────────────────────────────────────────────
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _det_uuid(name: str) -> str:
    return str(uuid.uuid5(_NS, name))


NOW = datetime.now(timezone.utc)


# ── Synthetic data builders ───────────────────────────────────────────────────

def _build_policies():
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
        },
        {
            "id": _det_uuid("policy-003"),
            "name": "Minimum Stay Policy",
            "version": "3.0",
            "description": "Minimum 2-night stay required during peak season (Jun-Aug).",
            "document_url": "https://docs.example.com/policies/min-stay-v3.0.pdf",
            "effective_from": NOW - timedelta(days=730),
            "effective_to": None,
            "is_active": True,
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
        },
        {
            "id": _det_uuid("policy-005"),
            "name": "Noise Curfew Policy",
            "version": "2.0",
            "description": "Quiet hours enforced 22:00-08:00 in all residential zones.",
            "document_url": "https://docs.example.com/policies/noise-curfew-v2.0.pdf",
            "effective_from": NOW - timedelta(days=270),
            "effective_to": None,
            "is_active": True,
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
        },
    ]


def _build_restrictions():
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
        },
    ]


def _build_evidence(restrictions):
    items = []
    for i, restr in enumerate(restrictions[:4]):
        items.append({
            "id": _det_uuid(f"evidence-{i+1:03d}-a"),
            "restriction_id": restr["id"],
            "source_table": "incident_reports",
            "source_record_id": _det_uuid(f"incident-{i+1:03d}"),
            "source_field": "violation_type",
            "evidence_value": f"Violation recorded for restriction: {restr['name']}",
            "confidence_score": round(0.75 + i * 0.05, 2),
            "collected_at": NOW - timedelta(days=30 + i * 10),
            "is_active": True,
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
        })
    return items


def _build_approval_requests(restrictions):
    statuses = ["pending", "pending", "escalated", "approved", "rejected", "pending"]
    priorities = ["high", "medium", "high", "low", "medium", "high"]
    queue_types = [
        "high_risk", "low_confidence", "high_risk",
        "low_confidence", "high_risk", "low_confidence",
    ]
    items = []
    for i in range(6):
        restr = restrictions[i % len(restrictions)]
        st = statuses[i]
        decided_at = (NOW - timedelta(days=5 + i)) if st in ("approved", "rejected") else None
        items.append({
            "id": _det_uuid(f"approval-{i+1:03d}"),
            "restriction_query_id": restr["id"],
            "risk_score": round(0.6 + i * 0.06, 2),
            "confidence_score": round(0.55 + i * 0.07, 2),
            "queue_type": queue_types[i],
            "priority": priorities[i],
            "status": st,
            "assigned_to": None,
            "decision_rationale": (
                f"Auto-generated rationale for approval request {i+1}"
                if st in ("approved", "rejected") else None
            ),
            "decided_at": decided_at,
            "context_data": json.dumps({"demo": True, "index": i + 1}),
            "is_active": True,
        })
    return items


def _build_users():
    """Build default admin and operator users."""
    # Import here to avoid issues at module load time
    from backend.src.core.security import hash_password
    return [
        {
            "id": _det_uuid("user-admin-001"),
            "email": "admin@example.com",
            "hashed_password": hash_password("admin-password"),
            "role": "admin",
            "is_active": True,
        },
        {
            "id": _det_uuid("user-operator-001"),
            "email": "operator@example.com",
            "hashed_password": hash_password("operator-password"),
            "role": "operator",
            "is_active": True,
        },
    ]


# ── Seed logic ────────────────────────────────────────────────────────────────

async def _has_existing_data(session: AsyncSession) -> bool:
    """Return True if any policies already exist."""
    from backend.src.models.policy import Policy
    result = await session.execute(select(Policy).limit(1))
    return result.scalar_one_or_none() is not None


async def _truncate_tables(session: AsyncSession) -> None:
    """Truncate non-audit, non-user tables in dependency order."""
    tables = [
        "messages",
        "conversations",
        "approval_requests",
        "evidence",
        "restrictions",
        "policies",
    ]
    for table in tables:
        await session.execute(text(f"DELETE FROM {table}"))  # noqa: S608
        logger.info("Truncated: %s", table)
    await session.flush()


async def _seed_users(session: AsyncSession) -> int:
    """Insert users if they don't already exist."""
    from backend.src.models.user import User
    users = _build_users()
    inserted = 0
    for u in users:
        existing = await session.execute(
            select(User).where(User.id == u["id"])
        )
        if existing.scalar_one_or_none() is None:
            obj = User(
                id=u["id"],
                email=u["email"],
                hashed_password=u["hashed_password"],
                role=u["role"],
                is_active=u["is_active"],
            )
            session.add(obj)
            inserted += 1
    await session.flush()
    return inserted


async def _seed_data(session: AsyncSession) -> dict:
    """Insert all synthetic records and return a summary."""
    from backend.src.models.policy import Policy
    from backend.src.models.restriction import Restriction
    from backend.src.models.evidence import Evidence
    from backend.src.models.approval_request import ApprovalRequest

    policies = _build_policies()
    restrictions = _build_restrictions()
    evidence_items = _build_evidence(restrictions)
    approval_requests = _build_approval_requests(restrictions)

    for p in policies:
        session.add(Policy(
            id=p["id"],
            name=p["name"],
            version=p["version"],
            description=p["description"],
            document_url=p["document_url"],
            effective_from=p["effective_from"],
            effective_to=p["effective_to"],
            is_active=p["is_active"],
        ))
    await session.flush()

    for r in restrictions:
        session.add(Restriction(
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
        ))
    await session.flush()

    for e in evidence_items:
        session.add(Evidence(
            id=e["id"],
            restriction_id=e["restriction_id"],
            source_table=e["source_table"],
            source_record_id=e["source_record_id"],
            source_field=e["source_field"],
            evidence_value=e["evidence_value"],
            confidence_score=e["confidence_score"],
            collected_at=e["collected_at"],
        ))
    await session.flush()

    for a in approval_requests:
        session.add(ApprovalRequest(
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
        ))
    await session.flush()

    all_ids = (
        [p["id"] for p in policies]
        + [r["id"] for r in restrictions]
        + [e["id"] for e in evidence_items]
        + [a["id"] for a in approval_requests]
    )
    checksum = hashlib.sha256("|".join(sorted(all_ids)).encode()).hexdigest()

    return {
        "policies": len(policies),
        "restrictions": len(restrictions),
        "evidence_items": len(evidence_items),
        "approval_requests": len(approval_requests),
        "total_records": len(all_ids),
        "validation_checksum": checksum,
    }


async def run_seed(force: bool = False) -> None:
    """Main seed entry point."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Ensure tables exist
    from backend.src.models.base import Base
    import backend.src.models  # noqa: F401 — register all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables ensured.")

    async with session_factory() as session:
        # Seed users (always idempotent)
        user_count = await _seed_users(session)
        logger.info("Users: %d inserted (skipped if already existed)", user_count)

        if not force:
            has_data = await _has_existing_data(session)
            if has_data:
                logger.info(
                    "Existing data detected. Skipping seed. Use --force to truncate and reseed."
                )
                await session.commit()
                await engine.dispose()
                return

        if force:
            await _truncate_tables(session)

        summary = await _seed_data(session)
        await session.commit()

    logger.info("Seed complete: %s", summary)
    logger.info("Validation checksum: %s", summary["validation_checksum"])
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed synthetic demo data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Truncate existing non-audit data before seeding",
    )
    args = parser.parse_args()
    asyncio.run(run_seed(force=args.force))
