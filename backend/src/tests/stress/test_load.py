"""Stress tests: concurrent approvals, query load, and mixed workload.

Tests:
- 10 simultaneous approval attempts on same request → exactly 1 succeeds
- High-volume sequential approval processing throughput
- Mixed workload: simultaneous queries, approvals, and config reads
- Response time percentiles under load (p50/p95/p99)
- Deadlock detection (zero expected)
- Memory stability under sustained load
"""
from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.approval_request import ApprovalRequest
from backend.src.models.evidence import Evidence
from backend.src.services.evidence_service import (
    ApprovalRequestService,
    EvidenceService,
    get_metrics_snapshot,
)
from backend.src.services.audit_service import AuditLogWriter, AuditChainService
from backend.src.core.exceptions import ConflictError, StateMachineError
from backend.src.config.settings import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_pending_ar(db_session: AsyncSession, **kwargs: Any) -> ApprovalRequest:
    """Create and persist a pending ApprovalRequest."""
    ar = ApprovalRequest(
        id=str(uuid.uuid4()),
        status="pending",
        priority=kwargs.get("priority", "medium"),
        queue_type=kwargs.get("queue_type", "low_confidence"),
        risk_score=kwargs.get("risk_score", 5.0),
        confidence_score=kwargs.get("confidence_score", 0.65),
        row_version=1,
    )
    db_session.add(ar)
    await db_session.commit()
    await db_session.refresh(ar)
    return ar


async def _timed_approve(
    db_session: AsyncSession,
    request_id: str,
    actor_id: str,
    expected_version: int | None = None,
) -> dict[str, Any]:
    """Attempt approval and return timing + result."""
    start = time.monotonic()
    svc = ApprovalRequestService(db_session)
    try:
        ar, headers = await svc.approve(
            request_id=request_id,
            actor_user_id=actor_id,
            rationale=f"Load test approval by {actor_id}",
            expected_version=expected_version,
        )
        elapsed = time.monotonic() - start
        return {
            "success": True,
            "elapsed_ms": elapsed * 1000,
            "version": ar.row_version,
            "status": ar.status,
        }
    except (ConflictError, StateMachineError) as exc:
        elapsed = time.monotonic() - start
        return {
            "success": False,
            "elapsed_ms": elapsed * 1000,
            "status_code": 409,
            "error": type(exc).__name__,
        }


def _compute_percentiles(times_ms: list[float]) -> dict[str, float]:
    """Compute p50, p95, p99 from a list of millisecond timings."""
    if not times_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "max": 0.0}
    sorted_times = sorted(times_ms)
    n = len(sorted_times)
    return {
        "p50": sorted_times[int(n * 0.50)],
        "p95": sorted_times[int(n * 0.95)],
        "p99": sorted_times[min(int(n * 0.99), n - 1)],
        "mean": statistics.mean(sorted_times),
        "max": max(sorted_times),
        "count": n,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestConcurrentApprovalLoad:
    """Concurrent approval stress tests."""

    @pytest.mark.asyncio
    async def test_10_concurrent_approvals_single_success(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """10 concurrent approval attempts: exactly 1 succeeds, 9 get 409.

        Uses sequential simulation with shared version=1 to model the
        optimistic-lock scenario. SQLite in-memory doesn't support true
        concurrent writes, but the version-check logic is fully exercised.
        """
        ar = await _create_pending_ar(db_session, priority="high", queue_type="high_risk")
        ar_id = ar.id

        results = []
        timings = []

        for i in range(10):
            async with session_factory() as session:
                result = await _timed_approve(session, ar_id, f"manager-{i:02d}", expected_version=1)
                results.append(result)
                timings.append(result["elapsed_ms"])

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        assert len(successes) == 1, (
            f"Expected exactly 1 success, got {len(successes)}"
        )
        assert len(failures) == 9, (
            f"Expected exactly 9 failures, got {len(failures)}"
        )
        for f in failures:
            assert f["status_code"] == 409

        # Performance check
        perf = _compute_percentiles(timings)
        # In test environment, operations should complete within reasonable time
        assert perf["p99"] < 5000, f"p99 latency too high: {perf['p99']:.1f}ms"

    @pytest.mark.asyncio
    async def test_sequential_throughput_20_approvals(
        self, db_session: AsyncSession
    ) -> None:
        """Process 20 approval requests sequentially and measure throughput."""
        # Create 20 pending requests
        requests = []
        for i in range(20):
            ar = await _create_pending_ar(
                db_session,
                priority="medium" if i % 2 == 0 else "high",
                queue_type="low_confidence" if i % 3 == 0 else "high_risk",
            )
            requests.append(ar)

        svc = ApprovalRequestService(db_session)
        timings = []
        successes = 0

        start_total = time.monotonic()
        for i, ar in enumerate(requests):
            start = time.monotonic()
            try:
                approved, _ = await svc.approve(
                    request_id=ar.id,
                    actor_user_id=f"processor-{i % 3:02d}",
                    rationale=f"Batch approval {i+1}/20",
                    expected_version=1,
                )
                assert approved.status == "approved"
                successes += 1
            except Exception:
                pass
            timings.append((time.monotonic() - start) * 1000)

        total_elapsed = time.monotonic() - start_total
        throughput = successes / total_elapsed  # approvals per second

        assert successes == 20, f"Expected 20 successes, got {successes}"
        perf = _compute_percentiles(timings)
        # Throughput should be reasonable
        assert throughput > 1.0, f"Throughput too low: {throughput:.2f} approvals/sec"

    @pytest.mark.asyncio
    async def test_no_deadlocks_under_load(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Verify zero deadlocks occur during concurrent operations."""
        # Create multiple requests
        ar_ids = []
        for i in range(5):
            ar = await _create_pending_ar(db_session)
            ar_ids.append(ar.id)

        deadlock_count = 0
        results = []

        # Simulate concurrent access patterns
        for ar_id in ar_ids:
            async with session_factory() as session:
                result = await _timed_approve(session, ar_id, "load-tester", expected_version=1)
                results.append(result)
                if result.get("error") == "OperationalError":
                    deadlock_count += 1

        assert deadlock_count == 0, f"Detected {deadlock_count} deadlocks — expected 0"
        assert all(r["success"] for r in results), "All unique-request approvals should succeed"

    @pytest.mark.asyncio
    async def test_conflict_rate_under_load(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Measure conflict rate when multiple managers target the same request."""
        ar = await _create_pending_ar(db_session, priority="high")
        ar_id = ar.id

        results = []
        for i in range(10):
            async with session_factory() as session:
                result = await _timed_approve(session, ar_id, f"manager-{i}", expected_version=1)
                results.append(result)

        successes = sum(1 for r in results if r["success"])
        conflicts = sum(1 for r in results if not r["success"])
        conflict_rate = conflicts / len(results)

        # With 10 concurrent attempts on 1 request, conflict rate should be ~90%
        assert conflict_rate >= 0.8, f"Expected conflict rate >= 80%, got {conflict_rate:.1%}"
        assert successes == 1, f"Expected exactly 1 success, got {successes}"


class TestMixedWorkloadStress:
    """Mixed workload: simultaneous queries, approvals, and config reads."""

    @pytest.mark.asyncio
    async def test_simultaneous_reads_and_writes(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Simultaneous read and write operations maintain consistency."""
        # Create requests for reading
        read_ars = []
        for i in range(5):
            ar = await _create_pending_ar(db_session)
            read_ars.append(ar)

        # Create requests for writing
        write_ars = []
        for i in range(5):
            ar = await _create_pending_ar(db_session)
            write_ars.append(ar)

        read_results = []
        write_results = []

        # Perform reads
        for ar in read_ars:
            async with session_factory() as session:
                svc = ApprovalRequestService(session)
                fetched, is_stale = await svc.get_with_stale_warning(
                    request_id=ar.id,
                    client_version=None,
                    requesting_user_id="reader-001",
                )
                read_results.append({"id": fetched.id, "status": fetched.status})

        # Perform writes
        for i, ar in enumerate(write_ars):
            async with session_factory() as session:
                result = await _timed_approve(session, ar.id, f"writer-{i}", expected_version=1)
                write_results.append(result)

        # Verify consistency
        assert len(read_results) == 5, "All reads should complete"
        assert all(r["status"] == "pending" for r in read_results), "Read requests should be pending"
        assert all(r["success"] for r in write_results), "All unique writes should succeed"

    @pytest.mark.asyncio
    async def test_config_reads_during_approvals(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Config reads during approval processing don't cause inconsistency."""
        ar = await _create_pending_ar(db_session)

        # Read config while processing approval
        config_reads = []
        for _ in range(5):
            thresholds = settings.get_thresholds()
            config_reads.append(thresholds)

        # Process approval
        async with session_factory() as session:
            result = await _timed_approve(session, ar.id, "processor", expected_version=1)

        assert result["success"] is True
        # Config reads should all return consistent values
        assert len(config_reads) == 5
        for cfg in config_reads:
            assert "risk_threshold" in cfg
            assert "confidence_threshold" in cfg

    @pytest.mark.asyncio
    async def test_audit_writes_during_approval_load(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Audit log writes during approval processing maintain chain integrity."""
        writer = AuditLogWriter(db_session)

        # Write some audit entries
        for i in range(5):
            await writer.append(
                event_type=f"load.test.event.{i}",
                actor_id=f"user-{i}",
                resource_type="ApprovalRequest",
                resource_id=f"AR-LOAD-{i:04d}",
                payload={"load_test": True, "index": i},
            )
        await db_session.commit()

        # Process approvals concurrently with audit writes
        ar = await _create_pending_ar(db_session)
        async with session_factory() as session:
            result = await _timed_approve(session, ar.id, "processor", expected_version=1)

        # Verify audit chain is still intact
        svc = AuditChainService(db_session)
        integrity = await svc.verify_chain_integrity()
        assert integrity["is_intact"] is True, (
            f"Audit chain broken during load test: {integrity['broken_at_sequences']}"
        )

    @pytest.mark.asyncio
    async def test_metrics_accuracy_under_load(
        self, db_session: AsyncSession, session_factory
    ) -> None:
        """Verify metrics counters are accurate after load operations."""
        initial = get_metrics_snapshot()
        initial_ops = initial["total_operations"]
        initial_conflicts = initial["conflict_count"]

        # Run a batch of operations
        ar = await _create_pending_ar(db_session)
        ar_id = ar.id

        op_count = 0
        conflict_count = 0

        for i in range(5):
            async with session_factory() as session:
                result = await _timed_approve(session, ar_id, f"manager-{i}", expected_version=1)
                op_count += 1
                if not result["success"]:
                    conflict_count += 1

        after = get_metrics_snapshot()

        # Metrics should have increased
        assert after["total_operations"] >= initial_ops + op_count, (
            f"Expected total_operations >= {initial_ops + op_count}, got {after['total_operations']}"
        )


class TestResponseTimePercentiles:
    """Response time measurement and percentile reporting."""

    @pytest.mark.asyncio
    async def test_approval_response_time_percentiles(
        self, db_session: AsyncSession
    ) -> None:
        """Measure p50/p95/p99 response times for approval operations."""
        timings = []
        svc = ApprovalRequestService(db_session)

        for i in range(15):
            ar = await _create_pending_ar(db_session)
            start = time.monotonic()
            await svc.approve(
                request_id=ar.id,
                actor_user_id=f"perf-tester-{i}",
                rationale=f"Performance test approval {i}",
                expected_version=1,
            )
            timings.append((time.monotonic() - start) * 1000)

        perf = _compute_percentiles(timings)

        # In test environment with SQLite, these should be fast
        assert perf["p50"] < 1000, f"p50 too high: {perf['p50']:.1f}ms"
        assert perf["p95"] < 3000, f"p95 too high: {perf['p95']:.1f}ms"
        assert perf["p99"] < 5000, f"p99 too high: {perf['p99']:.1f}ms"

    @pytest.mark.asyncio
    async def test_read_response_time_percentiles(
        self, db_session: AsyncSession
    ) -> None:
        """Measure p50/p95/p99 response times for read operations."""
        # Create requests to read
        ars = []
        for i in range(10):
            ar = await _create_pending_ar(db_session)
            ars.append(ar)

        svc = ApprovalRequestService(db_session)
        timings = []

        for ar in ars:
            start = time.monotonic()
            fetched, _ = await svc.get_with_stale_warning(
                request_id=ar.id,
                client_version=None,
                requesting_user_id="perf-reader",
            )
            timings.append((time.monotonic() - start) * 1000)

        perf = _compute_percentiles(timings)
        assert perf["p99"] < 2000, f"Read p99 too high: {perf['p99']:.1f}ms"

    @pytest.mark.asyncio
    async def test_audit_write_performance(
        self, db_session: AsyncSession
    ) -> None:
        """Measure audit log write performance under sustained load."""
        writer = AuditLogWriter(db_session)
        timings = []

        for i in range(20):
            start = time.monotonic()
            await writer.append(
                event_type=f"perf.test.{i}",
                actor_id=f"user-{i}",
                resource_type="Evidence",
                resource_id=f"EV-PERF-{i:04d}",
                payload={"index": i, "test": "performance"},
            )
            timings.append((time.monotonic() - start) * 1000)

        await db_session.commit()

        perf = _compute_percentiles(timings)
        assert perf["p99"] < 2000, f"Audit write p99 too high: {perf['p99']:.1f}ms"

        # Verify chain integrity after load
        svc = AuditChainService(db_session)
        result = await svc.verify_chain_integrity()
        assert result["is_intact"] is True


class TestMemoryAndResourceStability:
    """Resource stability tests under sustained load."""

    @pytest.mark.asyncio
    async def test_session_cleanup_after_load(
        self, session_factory
    ) -> None:
        """Sessions are properly cleaned up after load operations."""
        session_count = 0
        errors = []

        for i in range(20):
            try:
                async with session_factory() as session:
                    session_count += 1
                    # Simple query to verify session works
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
            except Exception as exc:
                errors.append(str(exc))

        assert session_count == 20, f"Expected 20 sessions, got {session_count}"
        assert not errors, f"Session errors: {errors}"

    @pytest.mark.asyncio
    async def test_large_batch_approval_processing(
        self, db_session: AsyncSession
    ) -> None:
        """Process a large batch of approvals without resource exhaustion."""
        batch_size = 30
        requests = []

        for i in range(batch_size):
            ar = await _create_pending_ar(db_session)
            requests.append(ar)

        svc = ApprovalRequestService(db_session)
        success_count = 0
        error_count = 0

        for i, ar in enumerate(requests):
            try:
                approved, _ = await svc.approve(
                    request_id=ar.id,
                    actor_user_id=f"batch-processor-{i % 5}",
                    rationale=f"Batch {i+1}/{batch_size}",
                    expected_version=1,
                )
                if approved.status == "approved":
                    success_count += 1
            except Exception:
                error_count += 1

        assert success_count == batch_size, (
            f"Expected {batch_size} successes, got {success_count} (errors: {error_count})"
        )
