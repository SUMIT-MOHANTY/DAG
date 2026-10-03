"""Evidence API endpoints — CRUD + ApprovalRequest state-machine actions.

All mutating endpoints (PUT, PATCH) honour the ``If-Match`` / ``X-Row-Version``
header for optimistic concurrency control.  A stale version returns HTTP 409
with the current server-side state embedded in the response body.

Second exception path (concurrent modification)
------------------------------------------------
PATCH /approvals/{id}/approve   — Manager A & B race on the same request.
The first writer wins; the second receives 409 + current_state.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.database import get_db
from backend.src.core.exceptions import ConflictError, StateMachineError
from backend.src.core.security import get_current_user
from backend.src.middleware.concurrency import build_version_headers
from backend.src.models.user import User
from backend.src.services.evidence_service import (
    ApprovalRequestService,
    EvidenceService,
    get_metrics_snapshot,
)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class EvidenceCreateRequest(BaseModel):
    restriction_id: str
    source_table: str
    source_record_id: str
    source_field: str
    evidence_value: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class EvidenceUpdateRequest(BaseModel):
    evidence_value: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_field: Optional[str] = None


class ApprovalActionRequest(BaseModel):
    rationale: str = Field(..., min_length=5, max_length=2000)
    expected_version: Optional[int] = Field(
        None,
        description="Row version the client last observed. Omit to skip optimistic-lock check.",
    )


class ConflictResponse(BaseModel):
    error: str
    detail: dict[str, Any]


# ── Helper: extract version from header OR body ───────────────────────────────

def _resolve_version(
    request: Request,
    body_version: Optional[int],
) -> Optional[int]:
    """Prefer the header version; fall back to the body field."""
    header_version: Optional[int] = getattr(request.state, "expected_version", None)
    return header_version if header_version is not None else body_version


# ── Evidence endpoints ────────────────────────────────────────────────────────

@router.post(
    "/evidence",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new evidence record",
    tags=["evidence"],
)
async def create_evidence(
    payload: EvidenceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    svc = EvidenceService(db)
    ev = await svc.create(
        restriction_id=payload.restriction_id,
        source_table=payload.source_table,
        source_record_id=payload.source_record_id,
        source_field=payload.source_field,
        evidence_value=payload.evidence_value,
        confidence_score=payload.confidence_score,
    )
    return {
        "id": ev.id,
        "restriction_id": ev.restriction_id,
        "source_table": ev.source_table,
        "source_record_id": ev.source_record_id,
        "source_field": ev.source_field,
        "evidence_value": ev.evidence_value,
        "confidence_score": ev.confidence_score,
        "collected_at": ev.collected_at.isoformat(),
        "row_version": ev.row_version,
    }


@router.get(
    "/evidence/{evidence_id}",
    summary="Retrieve a single evidence record",
    tags=["evidence"],
)
async def get_evidence(
    evidence_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    svc = EvidenceService(db)
    ev = await svc.get_by_id(evidence_id)
    # Advertise current version so client can send it back on mutation
    for k, v in build_version_headers(ev.row_version).items():
        response.headers[k] = v
    return {
        "id": ev.id,
        "restriction_id": ev.restriction_id,
        "source_table": ev.source_table,
        "source_record_id": ev.source_record_id,
        "source_field": ev.source_field,
        "evidence_value": ev.evidence_value,
        "confidence_score": ev.confidence_score,
        "collected_at": ev.collected_at.isoformat(),
        "row_version": ev.row_version,
        "created_at": ev.created_at.isoformat(),
        "updated_at": ev.updated_at.isoformat(),
    }


@router.patch(
    "/evidence/{evidence_id}",
    summary="Update an evidence record (optimistic locking)",
    tags=["evidence"],
    responses={
        409: {"model": ConflictResponse, "description": "Concurrent modification detected"},
    },
)
async def update_evidence(
    evidence_id: str,
    payload: EvidenceUpdateRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    if_match: Optional[str] = Header(None, alias="If-Match"),
) -> dict[str, Any]:
    expected_version = _resolve_version(request, None)
    svc = EvidenceService(db)
    ev, headers = await svc.update(
        evidence_id=evidence_id,
        expected_version=expected_version,
        **payload.model_dump(exclude_none=True),
    )
    for k, v in headers.items():
        response.headers[k] = v
    return {
        "id": ev.id,
        "evidence_value": ev.evidence_value,
        "confidence_score": ev.confidence_score,
        "source_field": ev.source_field,
        "row_version": ev.row_version,
        "updated_at": ev.updated_at.isoformat(),
    }


# ── ApprovalRequest state-machine endpoints ───────────────────────────────────

@router.get(
    "/approvals/{request_id}",
    summary="Get approval request (with stale-version warning)",
    tags=["approvals"],
)
async def get_approval_request(
    request_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    client_version = getattr(request.state, "expected_version", None)
    svc = ApprovalRequestService(db)
    ar, is_stale = await svc.get_with_stale_warning(
        request_id=request_id,
        client_version=client_version,
        requesting_user_id=current_user.id,
    )
    for k, v in build_version_headers(ar.row_version).items():
        response.headers[k] = v
    if is_stale:
        response.headers["X-Stale-Data"] = "true"
    return {
        "id": ar.id,
        "status": ar.status,
        "priority": ar.priority,
        "queue_type": ar.queue_type,
        "risk_score": ar.risk_score,
        "confidence_score": ar.confidence_score,
        "assigned_to": ar.assigned_to,
        "decision_rationale": ar.decision_rationale,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "row_version": ar.row_version,
        "created_at": ar.created_at.isoformat(),
        "updated_at": ar.updated_at.isoformat(),
        "is_stale": is_stale,
    }


@router.patch(
    "/approvals/{request_id}/approve",
    summary="Approve an approval request (optimistic locking)",
    tags=["approvals"],
    responses={
        409: {"model": ConflictResponse, "description": "Concurrent modification — see current_state"},
    },
)
async def approve_request(
    request_id: str,
    payload: ApprovalActionRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve an ApprovalRequest.

    **Second exception path**: if another manager already acted on this request
    (version mismatch), returns HTTP 409 with the current server-side state so
    the client can refresh and decide whether further action is needed.
    """
    expected_version = _resolve_version(request, payload.expected_version)
    svc = ApprovalRequestService(db)
    ar, headers = await svc.approve(
        request_id=request_id,
        actor_user_id=current_user.id,
        rationale=payload.rationale,
        expected_version=expected_version,
    )
    for k, v in headers.items():
        response.headers[k] = v
    return {
        "id": ar.id,
        "status": ar.status,
        "row_version": ar.row_version,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "decided_by": ar.assigned_to,
        "decision_rationale": ar.decision_rationale,
    }


@router.patch(
    "/approvals/{request_id}/reject",
    summary="Reject an approval request (optimistic locking)",
    tags=["approvals"],
    responses={
        409: {"model": ConflictResponse, "description": "Concurrent modification — see current_state"},
    },
)
async def reject_request(
    request_id: str,
    payload: ApprovalActionRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject an ApprovalRequest.

    **Second exception path**: stale version → HTTP 409 + current_state.
    """
    expected_version = _resolve_version(request, payload.expected_version)
    svc = ApprovalRequestService(db)
    ar, headers = await svc.reject(
        request_id=request_id,
        actor_user_id=current_user.id,
        rationale=payload.rationale,
        expected_version=expected_version,
    )
    for k, v in headers.items():
        response.headers[k] = v
    return {
        "id": ar.id,
        "status": ar.status,
        "row_version": ar.row_version,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "decided_by": ar.assigned_to,
        "decision_rationale": ar.decision_rationale,
    }


@router.patch(
    "/approvals/{request_id}/escalate",
    summary="Escalate an approval request (optimistic locking)",
    tags=["approvals"],
    responses={
        409: {"model": ConflictResponse, "description": "Concurrent modification — see current_state"},
    },
)
async def escalate_request(
    request_id: str,
    payload: ApprovalActionRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    expected_version = _resolve_version(request, payload.expected_version)
    svc = ApprovalRequestService(db)
    ar, headers = await svc.escalate(
        request_id=request_id,
        actor_user_id=current_user.id,
        rationale=payload.rationale,
        expected_version=expected_version,
    )
    for k, v in headers.items():
        response.headers[k] = v
    return {
        "id": ar.id,
        "status": ar.status,
        "row_version": ar.row_version,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "decided_by": ar.assigned_to,
        "decision_rationale": ar.decision_rationale,
    }


@router.patch(
    "/approvals/{request_id}/withdraw",
    summary="Withdraw an approval request (optimistic locking)",
    tags=["approvals"],
    responses={
        409: {"model": ConflictResponse, "description": "Concurrent modification — see current_state"},
    },
)
async def withdraw_request(
    request_id: str,
    payload: ApprovalActionRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    expected_version = _resolve_version(request, payload.expected_version)
    svc = ApprovalRequestService(db)
    ar, headers = await svc.withdraw(
        request_id=request_id,
        actor_user_id=current_user.id,
        rationale=payload.rationale,
        expected_version=expected_version,
    )
    for k, v in headers.items():
        response.headers[k] = v
    return {
        "id": ar.id,
        "status": ar.status,
        "row_version": ar.row_version,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "decided_by": ar.assigned_to,
        "decision_rationale": ar.decision_rationale,
    }


# ── Metrics endpoint ──────────────────────────────────────────────────────────

@router.get(
    "/approvals/metrics/concurrency",
    summary="Concurrency execution metrics",
    tags=["approvals", "metrics"],
)
async def concurrency_metrics(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return live concurrency metrics: conflict rate, retry success rate,
    average stale-read resolution time.
    """
    return get_metrics_snapshot()
