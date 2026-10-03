"""Evidence service — concurrent-safe CRUD and approval-request state machine.

This module owns:
- Evidence CRUD with optimistic-locking version checks.
- ApprovalRequest state machine (approve / reject / escalate / withdraw).
- Retry decorator with exponential back-off for transient DB conflicts.
- Execution metrics: conflict rate, retry success rate, average resolution time.
- Notification stubs for conflict alerts and stale-data warnings.

Second exception path (concurrent modification)
------------------------------------------------
Manager A loads AR-001 at version=3.
Manager B loads AR-001 at version=3.
Manager B approves  → version bumped to 4, status=approved.
Manager A rejects   → sends expected_version=3.
Service calls verify_version(expected=3, actual=4) → raises ConflictError(409)
with current_state={id, status, row_version, decided_by, decided_at}.
Manager A receives 409 + current_state and can refresh before acting.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    ConflictError,
    NotFoundError,
    StateMachineError,
    ValidationError,
)
from backend.src.middleware.concurrency import build_version_headers, verify_version
from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.evidence import Evidence

logger = logging.getLogger(__name__)


# ── State machine definition ──────────────────────────────────────────────────

# Maps current_status → set of valid next statuses
APPROVAL_TRANSITIONS: dict[str, set[str]] = {
    "pending":    {"approved", "rejected", "escalated", "withdrawn"},
    "escalated":  {"approved", "rejected", "withdrawn"},
    "approved":   set(),          # terminal — no further transitions
    "rejected":   set(),          # terminal
    "withdrawn":  set(),          # terminal
}


def _assert_transition(current: str, target: str, resource_id: str) -> None:
    """Raise StateMachineError if the transition is not permitted."""
    allowed = APPROVAL_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise StateMachineError(
            resource=f"ApprovalRequest({resource_id})",
            from_state=current,
            to_state=target,
            allowed_transitions=sorted(allowed),
        )


# ── Retry decorator ───────────────────────────────────────────────────────────

def _retry_on_transient(
    max_attempts: int = 3,
    base_delay: float = 0.1,
    backoff_factor: float = 2.0,
) -> Any:
    """Async decorator: retry on transient OperationalError with exponential back-off.

    ConflictError (optimistic-lock failure) is *not* retried — it must be
    surfaced to the caller so the client can refresh.
    """
    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except ConflictError:
                    # Optimistic-lock conflicts are not transient — re-raise immediately
                    raise
                except OperationalError as exc:
                    if attempt == max_attempts:
                        logger.error(
                            "Transient DB error after %d attempts: %s", max_attempts, exc
                        )
                        raise
                    logger.warning(
                        "Transient DB error (attempt %d/%d), retrying in %.2fs: %s",
                        attempt, max_attempts, delay, exc,
                    )
                    _metrics.record_retry()
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator


# ── Execution metrics ─────────────────────────────────────────────────────────

class _ConflictMetrics:
    """In-process metrics store for conflict / retry / resolution tracking.

    In production these would be emitted to Prometheus / OpenTelemetry.
    A rolling window of the last 1 000 operations is kept in memory.
    """

    _WINDOW = 1_000

    def __init__(self) -> None:
        self._total_ops: int = 0
        self._conflict_count: int = 0
        self._retry_count: int = 0
        self._retry_success_count: int = 0
        # Deque of resolution times in seconds (stale-read → conflict detected)
        self._resolution_times: deque[float] = deque(maxlen=self._WINDOW)
        self._stale_read_timestamps: dict[str, float] = {}  # request_id → wall time

    # -- recording helpers --

    def record_operation(self) -> None:
        self._total_ops += 1

    def record_conflict(self, request_id: str) -> None:
        self._conflict_count += 1
        start = self._stale_read_timestamps.pop(request_id, None)
        if start is not None:
            self._resolution_times.append(time.monotonic() - start)

    def record_stale_read(self, request_id: str) -> None:
        """Call when a resource is fetched (potential stale-read window opens)."""
        self._stale_read_timestamps[request_id] = time.monotonic()

    def record_retry(self) -> None:
        self._retry_count += 1

    def record_retry_success(self) -> None:
        self._retry_success_count += 1

    # -- computed properties --

    @property
    def conflict_rate(self) -> float:
        """Fraction of operations that resulted in a conflict."""
        return self._conflict_count / self._total_ops if self._total_ops else 0.0

    @property
    def retry_success_rate(self) -> float:
        """Fraction of retries that eventually succeeded."""
        return (
            self._retry_success_count / self._retry_count
            if self._retry_count
            else 0.0
        )

    @property
    def avg_resolution_time(self) -> float:
        """Average stale-read window duration in seconds."""
        if not self._resolution_times:
            return 0.0
        return sum(self._resolution_times) / len(self._resolution_times)

    def snapshot(self) -> dict[str, Any]:
        return {
            "total_operations": self._total_ops,
            "conflict_count": self._conflict_count,
            "conflict_rate": round(self.conflict_rate, 4),
            "retry_count": self._retry_count,
            "retry_success_count": self._retry_success_count,
            "retry_success_rate": round(self.retry_success_rate, 4),
            "avg_resolution_time_seconds": round(self.avg_resolution_time, 4),
        }


_metrics = _ConflictMetrics()


def get_metrics_snapshot() -> dict[str, Any]:
    """Return a point-in-time snapshot of concurrency metrics."""
    return _metrics.snapshot()


# ── Notification stubs ────────────────────────────────────────────────────────

async def _notify_conflict(
    request_id: str,
    loser_user_id: str,
    winner_user_id: str,
    current_state: dict[str, Any],
) -> None:
    """Emit a conflict-alert notification (stub — replace with real transport)."""
    logger.warning(
        "CONFLICT ALERT | ApprovalRequest=%s | loser=%s | winner=%s | current_state=%s",
        request_id,
        loser_user_id,
        winner_user_id,
        current_state,
    )
    # TODO: publish to WebSocket channel / email / Slack


async def _notify_stale_data(user_id: str, request_id: str, stale_version: int) -> None:
    """Warn a user that the data they are viewing is stale."""
    logger.info(
        "STALE DATA WARNING | user=%s | ApprovalRequest=%s | stale_version=%d",
        user_id,
        request_id,
        stale_version,
    )
    # TODO: push via WebSocket / SSE


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _approval_state_dict(ar: ApprovalRequest) -> dict[str, Any]:
    """Serialise an ApprovalRequest to a plain dict for 409 current_state payloads."""
    return {
        "id": ar.id,
        "status": ar.status,
        "row_version": ar.row_version,
        "assigned_to": ar.assigned_to,
        "decided_at": ar.decided_at.isoformat() if ar.decided_at else None,
        "decision_rationale": ar.decision_rationale,
        "priority": ar.priority,
        "queue_type": ar.queue_type,
        "updated_at": ar.updated_at.isoformat() if ar.updated_at else None,
    }


# ── Evidence CRUD ─────────────────────────────────────────────────────────────

class EvidenceService:
    """CRUD operations for Evidence records with optimistic-locking support."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, evidence_id: str) -> Evidence:
        result = await self.db.execute(
            select(Evidence).where(Evidence.id == evidence_id, Evidence.is_active.is_(True))
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            raise NotFoundError("Evidence", evidence_id)
        return ev

    async def list_by_restriction(
        self, restriction_id: str, skip: int = 0, limit: int = 100
    ) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(
                Evidence.restriction_id == restriction_id,
                Evidence.is_active.is_(True),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @_retry_on_transient()
    async def create(
        self,
        restriction_id: str,
        source_table: str,
        source_record_id: str,
        source_field: str,
        evidence_value: Optional[str] = None,
        confidence_score: Optional[float] = None,
        collected_at: Optional[datetime] = None,
    ) -> Evidence:
        ev = Evidence(
            id=str(uuid.uuid4()),
            restriction_id=restriction_id,
            source_table=source_table,
            source_record_id=source_record_id,
            source_field=source_field,
            evidence_value=evidence_value,
            confidence_score=confidence_score,
            collected_at=collected_at or datetime.now(timezone.utc),
            row_version=1,
        )
        self.db.add(ev)
        await self.db.commit()
        await self.db.refresh(ev)
        _metrics.record_operation()
        return ev

    @_retry_on_transient()
    async def update(
        self,
        evidence_id: str,
        expected_version: Optional[int],
        **fields: Any,
    ) -> tuple[Evidence, dict[str, str]]:
        """Update an Evidence record with optimistic-locking check.

        Returns the updated record and version response headers.
        """
        _metrics.record_operation()
        _metrics.record_stale_read(evidence_id)
        ev = await self.get_by_id(evidence_id)
        current_state = {
            "id": ev.id,
            "row_version": ev.row_version,
            "restriction_id": ev.restriction_id,
        }
        try:
            verify_version(
                expected=expected_version,
                actual=ev.row_version,
                current_state=current_state,
                resource_label=f"Evidence({evidence_id})",
            )
        except ConflictError:
            _metrics.record_conflict(evidence_id)
            raise

        for key, value in fields.items():
            if hasattr(ev, key):
                setattr(ev, key, value)
        # row_version is bumped by the SQLAlchemy before_update event listener
        await self.db.commit()
        await self.db.refresh(ev)
        _metrics.record_retry_success()
        return ev, build_version_headers(ev.row_version)

    @_retry_on_transient()
    async def soft_delete(self, evidence_id: str, expected_version: Optional[int]) -> None:
        ev = await self.get_by_id(evidence_id)
        verify_version(
            expected=expected_version,
            actual=ev.row_version,
            current_state={"id": ev.id, "row_version": ev.row_version},
            resource_label=f"Evidence({evidence_id})",
        )
        ev.is_active = False
        await self.db.commit()


# ── ApprovalRequest state-machine service ─────────────────────────────────────

class ApprovalRequestService:
    """Concurrent-safe state transitions for ApprovalRequest entities.

    All mutating methods accept an ``expected_version`` parameter.  When
    provided, an optimistic-lock check is performed before any state change.
    A ``ConflictError`` (HTTP 409) is raised if the version is stale, carrying
    the full current state so the client can refresh without an extra GET.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- internal helpers --

    async def _get_or_404(self, request_id: str) -> ApprovalRequest:
        result = await self.db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        ar = result.scalar_one_or_none()
        if ar is None:
            raise NotFoundError("ApprovalRequest", request_id)
        return ar

    def _check_version(
        self,
        ar: ApprovalRequest,
        expected_version: Optional[int],
        actor_user_id: str,
    ) -> None:
        """Verify optimistic lock and record metrics / notifications on conflict."""
        if expected_version is None:
            return
        if expected_version != ar.row_version:
            current_state = _approval_state_dict(ar)
            _metrics.record_conflict(ar.id)
            # Fire-and-forget notification (non-blocking)
            asyncio.create_task(
                _notify_conflict(
                    request_id=ar.id,
                    loser_user_id=actor_user_id,
                    winner_user_id=ar.assigned_to or "unknown",
                    current_state=current_state,
                )
            )
            raise ConflictError(
                message=(
                    f"ApprovalRequest {ar.id} was modified concurrently. "
                    f"Expected version {expected_version} but found version {ar.row_version}. "
                    "Refresh and retry."
                ),
                current_state=current_state,
                expected_version=expected_version,
                actual_version=ar.row_version,
            )

    # -- public state-machine methods --

    @_retry_on_transient()
    async def approve(
        self,
        request_id: str,
        actor_user_id: str,
        rationale: str,
        expected_version: Optional[int] = None,
    ) -> tuple[ApprovalRequest, dict[str, str]]:
        """Approve an ApprovalRequest.

        Raises
        ------
        NotFoundError        – request_id does not exist.
        StateMachineError    – current status does not allow approval.
        ConflictError (409)  – optimistic-lock version mismatch.
        """
        _metrics.record_operation()
        _metrics.record_stale_read(request_id)

        ar = await self._get_or_404(request_id)
        self._check_version(ar, expected_version, actor_user_id)
        _assert_transition(ar.status, "approved", request_id)

        ar.status = "approved"
        ar.assigned_to = actor_user_id
        ar.decision_rationale = rationale
        ar.decided_at = datetime.now(timezone.utc)
        # row_version bumped by before_update event on ApprovalRequest
        await self.db.commit()
        await self.db.refresh(ar)
        _metrics.record_retry_success()
        logger.info("ApprovalRequest %s approved by %s (version→%d)", ar.id, actor_user_id, ar.row_version)
        return ar, build_version_headers(ar.row_version)

    @_retry_on_transient()
    async def reject(
        self,
        request_id: str,
        actor_user_id: str,
        rationale: str,
        expected_version: Optional[int] = None,
    ) -> tuple[ApprovalRequest, dict[str, str]]:
        """Reject an ApprovalRequest."""
        _metrics.record_operation()
        _metrics.record_stale_read(request_id)

        ar = await self._get_or_404(request_id)
        self._check_version(ar, expected_version, actor_user_id)
        _assert_transition(ar.status, "rejected", request_id)

        ar.status = "rejected"
        ar.assigned_to = actor_user_id
        ar.decision_rationale = rationale
        ar.decided_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(ar)
        _metrics.record_retry_success()
        logger.info("ApprovalRequest %s rejected by %s (version→%d)", ar.id, actor_user_id, ar.row_version)
        return ar, build_version_headers(ar.row_version)

    @_retry_on_transient()
    async def escalate(
        self,
        request_id: str,
        actor_user_id: str,
        rationale: str,
        expected_version: Optional[int] = None,
    ) -> tuple[ApprovalRequest, dict[str, str]]:
        """Escalate an ApprovalRequest for senior review."""
        _metrics.record_operation()
        _metrics.record_stale_read(request_id)

        ar = await self._get_or_404(request_id)
        self._check_version(ar, expected_version, actor_user_id)
        _assert_transition(ar.status, "escalated", request_id)

        ar.status = "escalated"
        ar.decision_rationale = rationale
        ar.decided_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(ar)
        _metrics.record_retry_success()
        logger.info("ApprovalRequest %s escalated by %s (version→%d)", ar.id, actor_user_id, ar.row_version)
        return ar, build_version_headers(ar.row_version)

    @_retry_on_transient()
    async def withdraw(
        self,
        request_id: str,
        actor_user_id: str,
        rationale: str,
        expected_version: Optional[int] = None,
    ) -> tuple[ApprovalRequest, dict[str, str]]:
        """Withdraw (cancel) an ApprovalRequest."""
        _metrics.record_operation()
        _metrics.record_stale_read(request_id)

        ar = await self._get_or_404(request_id)
        self._check_version(ar, expected_version, actor_user_id)
        _assert_transition(ar.status, "withdrawn", request_id)

        ar.status = "withdrawn"
        ar.decision_rationale = rationale
        ar.decided_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(ar)
        _metrics.record_retry_success()
        logger.info("ApprovalRequest %s withdrawn by %s (version→%d)", ar.id, actor_user_id, ar.row_version)
        return ar, build_version_headers(ar.row_version)

    async def get_with_stale_warning(
        self,
        request_id: str,
        client_version: Optional[int],
        requesting_user_id: str,
    ) -> tuple[ApprovalRequest, bool]:
        """Fetch an ApprovalRequest and flag whether the client's copy is stale.

        Returns (record, is_stale).  When stale, a notification is dispatched.
        """
        ar = await self._get_or_404(request_id)
        _metrics.record_stale_read(request_id)
        is_stale = client_version is not None and client_version != ar.row_version
        if is_stale:
            asyncio.create_task(
                _notify_stale_data(requesting_user_id, request_id, client_version)  # type: ignore[arg-type]
            )
        return ar, is_stale
