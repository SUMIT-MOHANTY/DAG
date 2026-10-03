"""Admin API endpoints — audit trail, reseed, configuration, and health check.

Endpoints:
  POST /admin/reseed                  — truncate + regenerate synthetic data
  GET  /admin/audit/verify            — verify hash-chain integrity
  GET  /admin/audit                   — query audit logs with filters
  GET  /admin/audit/export            — export audit trail (JSON/CSV)
  GET  /admin/config                  — read current threshold configuration
  PUT  /admin/config                  — update threshold configuration
  POST /admin/config/reset            — reset thresholds to env-var defaults
  GET  /admin/health                  — detailed health check with dependency status
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.database import get_db
from backend.src.config.settings import settings
from backend.src.core.security import get_current_admin_user
from backend.src.models.evidence import HashChainedAuditLog
from backend.src.models.user import User
from backend.src.services.audit_service import AuditChainService
from backend.src.services.reseed_service import ReseedService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Request / Response schemas ────────────────────────────────────────────────

class ThresholdUpdateRequest(BaseModel):
    """Payload for PUT /admin/config."""
    risk_threshold: Optional[int] = Field(None, ge=1, le=5)
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_approve_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    high_risk_threshold: Optional[int] = Field(None, ge=1, le=5)


class ThresholdResponse(BaseModel):
    risk_threshold: int
    confidence_threshold: float
    auto_approve_confidence: float
    high_risk_threshold: int
    source: str = "effective"  # "effective" | "defaults"


class ReseedResponse(BaseModel):
    policies: int
    restrictions: int
    evidence_items: int
    approval_requests: int
    total_records: int
    validation_checksum: str
    reseeded_at: str


class AuditVerifyResponse(BaseModel):
    is_intact: bool
    total_records: int
    broken_at_sequences: list[int]
    missing_sequences: list[int]
    verified_at: str


class HealthResponse(BaseModel):
    status: str
    database: str
    threshold_config_valid: bool
    seed_data_checksum: Optional[str]
    audit_chain_intact: Optional[bool]
    checked_at: str
    details: dict[str, Any]


# ── POST /admin/reseed ────────────────────────────────────────────────────────

@router.post(
    "/reseed",
    response_model=ReseedResponse,
    status_code=status.HTTP_200_OK,
    summary="Truncate non-audit tables and regenerate synthetic demo data",
    responses={
        400: {"description": "Missing confirmation parameter"},
        403: {"description": "Admin role required"},
    },
)
async def reseed_data(
    confirm: bool = Query(
        False,
        description="Must be true to execute the reseed. Safety guard.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Truncate all non-audit tables and regenerate a consistent synthetic dataset.

    **Preserved**: users, hash_chained_audit_logs, audit_logs
    **Truncated**: policies, restrictions, evidence, approval_requests,
                   conversations, messages

    Pass ``?confirm=true`` to execute.  Without it the endpoint returns 400.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Reseed not executed. Pass ?confirm=true to confirm this destructive operation."
            ),
        )

    logger.warning(
        "Reseed initiated by admin user %s (%s)",
        current_user.id,
        current_user.email,
    )

    svc = ReseedService(db)
    summary = await svc.reseed()
    await db.commit()

    logger.info("Reseed completed: %s", summary)
    return summary


# ── GET /admin/audit/verify ───────────────────────────────────────────────────

@router.get(
    "/audit/verify",
    response_model=AuditVerifyResponse,
    summary="Verify hash-chain integrity of the audit log",
)
async def verify_audit_chain(
    start_seq: Optional[int] = Query(None, description="Start sequence number (inclusive)"),
    end_seq: Optional[int] = Query(None, description="End sequence number (inclusive)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Recompute every SHA-256 hash in the chain and report any breaks.

    Returns ``is_intact=true`` when no tampering is detected.
    """
    svc = AuditChainService(db)
    result = await svc.verify_chain_integrity(start_seq=start_seq, end_seq=end_seq)
    await db.commit()  # persist integrity_verified_at stamps
    return result


# ── GET /admin/audit ──────────────────────────────────────────────────────────

@router.get(
    "/audit",
    summary="Query audit logs with filters",
)
async def query_audit_logs(
    start_time: Optional[datetime] = Query(None, description="Filter: created_at >= start_time"),
    end_time: Optional[datetime] = Query(None, description="Filter: created_at <= end_time"),
    event_type: Optional[str] = Query(None, description="Filter by exact event_type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource_type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource_id"),
    integrity_status: Optional[str] = Query(
        None,
        description="Filter by integrity status: 'verified' | 'unverified' | 'all'",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Return paginated, filtered audit log records."""
    svc = AuditChainService(db)
    records, total = await svc.query_audit_logs(
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        integrity_status=integrity_status,
        skip=skip,
        limit=limit,
    )
    items = [
        {
            "id": r.id,
            "sequence_number": r.sequence_number,
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
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


# ── GET /admin/audit/export ───────────────────────────────────────────────────

@router.get(
    "/audit/export",
    summary="Export audit trail with integrity attestation (JSON or CSV)",
)
async def export_audit(
    format: str = Query("json", description="Export format: 'json' | 'csv'"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    event_type: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    include_attestation: bool = Query(True, description="Include integrity attestation block"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Response:
    """Stream the filtered audit trail as JSON or CSV with an integrity attestation."""
    if format not in ("json", "csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format must be 'json' or 'csv'",
        )

    svc = AuditChainService(db)
    content, media_type = await svc.export_audit(
        format=format,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        resource_type=resource_type,
        include_attestation=include_attestation,
    )

    ext = "csv" if format == "csv" else "json"
    filename = f"audit_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{ext}"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /admin/config ─────────────────────────────────────────────────────────

@router.get(
    "/config",
    response_model=ThresholdResponse,
    summary="Read current effective threshold configuration",
)
async def get_config(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Return the current effective threshold values (env defaults + any overrides)."""
    thresholds = settings.get_thresholds()
    return {
        **thresholds,
        "source": "effective",
    }


# ── PUT /admin/config ─────────────────────────────────────────────────────────

@router.put(
    "/config",
    response_model=ThresholdResponse,
    summary="Update threshold configuration (hot-reload, no restart required)",
    responses={
        422: {"description": "Invalid threshold combination"},
    },
)
async def update_config(
    payload: ThresholdUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Persist new threshold values and hot-reload without restarting the server.

    Validation rules enforced:
    - ``auto_approve_confidence`` >= ``confidence_threshold``
    - ``high_risk_threshold`` <= ``risk_threshold``
    """
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No threshold values provided.",
        )

    try:
        new_thresholds = settings.update_thresholds(updates)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    logger.info(
        "Threshold config updated by admin %s: %s",
        current_user.id,
        updates,
    )
    return {
        **new_thresholds,
        "source": "effective",
    }


# ── POST /admin/config/reset ──────────────────────────────────────────────────

@router.post(
    "/config/reset",
    response_model=ThresholdResponse,
    summary="Reset thresholds to environment-variable defaults",
)
async def reset_config(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Remove all threshold overrides and revert to the environment-variable defaults."""
    defaults = settings.reset_thresholds()
    logger.info("Threshold config reset to defaults by admin %s", current_user.id)
    return {
        **defaults,
        "source": "effective",
    }


# ── GET /admin/health ─────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Detailed health check: DB, thresholds, seed data, audit chain",
)
async def admin_health_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Return dependency health status including:
    - Database connectivity
    - Threshold configuration validity
    - Seed data checksum (record counts)
    - Audit chain integrity (last 100 records)
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    details: dict[str, Any] = {}
    overall_status = "healthy"

    # ── 1. Database connectivity ──────────────────────────────────────────────
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"
        overall_status = "degraded"
    details["database"] = db_status

    # ── 2. Threshold configuration validity ───────────────────────────────────
    threshold_valid = True
    threshold_detail: dict[str, Any] = {}
    try:
        thresholds = settings.get_thresholds()
        threshold_detail = thresholds
        # Re-validate by constructing a Settings instance
        from backend.src.config.settings import Settings  # local import
        Settings(**{**Settings().model_dump(), **thresholds})
    except Exception as exc:  # noqa: BLE001
        threshold_valid = False
        threshold_detail["error"] = str(exc)
        overall_status = "degraded"
    details["thresholds"] = threshold_detail

    # ── 3. Seed data checksum (record counts) ─────────────────────────────────
    seed_checksum: Optional[str] = None
    try:
        from backend.src.models.policy import Policy
        from backend.src.models.restriction import Restriction
        from backend.src.models.evidence import Evidence
        from backend.src.models.approval_request import ApprovalRequest

        policy_count_r = await db.execute(select(func.count()).select_from(Policy))
        restriction_count_r = await db.execute(select(func.count()).select_from(Restriction))
        evidence_count_r = await db.execute(select(func.count()).select_from(Evidence))
        approval_count_r = await db.execute(select(func.count()).select_from(ApprovalRequest))

        counts = {
            "policies": policy_count_r.scalar_one(),
            "restrictions": restriction_count_r.scalar_one(),
            "evidence_items": evidence_count_r.scalar_one(),
            "approval_requests": approval_count_r.scalar_one(),
        }
        seed_checksum = hashlib.sha256(
            "|".join(f"{k}:{v}" for k, v in sorted(counts.items())).encode()
        ).hexdigest()
        details["seed_data"] = {**counts, "checksum": seed_checksum}
    except Exception as exc:  # noqa: BLE001
        details["seed_data"] = {"error": str(exc)}
        overall_status = "degraded"

    # ── 4. Audit chain integrity (last 100 records) ───────────────────────────
    audit_chain_intact: Optional[bool] = None
    try:
        # Get the last 100 sequence numbers
        max_seq_r = await db.execute(
            select(func.max(HashChainedAuditLog.sequence_number))
        )
        max_seq: Optional[int] = max_seq_r.scalar_one_or_none()
        if max_seq is not None:
            start_seq = max(1, max_seq - 99)
            chain_svc = AuditChainService(db)
            chain_result = await chain_svc.verify_chain_integrity(
                start_seq=start_seq, end_seq=max_seq
            )
            audit_chain_intact = chain_result["is_intact"]
            details["audit_chain"] = {
                "records_checked": chain_result["total_records"],
                "is_intact": audit_chain_intact,
                "broken_at_sequences": chain_result["broken_at_sequences"],
                "missing_sequences": chain_result["missing_sequences"],
            }
            if not audit_chain_intact:
                overall_status = "degraded"
        else:
            details["audit_chain"] = {"records_checked": 0, "is_intact": True}
            audit_chain_intact = True
    except Exception as exc:  # noqa: BLE001
        details["audit_chain"] = {"error": str(exc)}
        overall_status = "degraded"

    return {
        "status": overall_status,
        "database": db_status,
        "threshold_config_valid": threshold_valid,
        "seed_data_checksum": seed_checksum,
        "audit_chain_intact": audit_chain_intact,
        "checked_at": checked_at,
        "details": details,
    }
