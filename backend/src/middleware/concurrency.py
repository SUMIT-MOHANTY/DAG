"""Concurrency middleware: optimistic-locking version header parsing and verification."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.src.core.exceptions import ConflictError


# ── Version header helpers ────────────────────────────────────────────────────

_VERSION_HEADER = "X-Row-Version"
_ETAG_HEADER = "ETag"
_IF_MATCH_HEADER = "If-Match"


def build_version_headers(row_version: int) -> dict[str, str]:
    """Build response headers advertising the current row version."""
    version_str = str(row_version)
    return {
        _VERSION_HEADER: version_str,
        _ETAG_HEADER: f'"{version_str}"',
    }


def verify_version(
    expected: Optional[int],
    actual: int,
    current_state: dict[str, Any],
    resource_label: str = "resource",
) -> None:
    """Raise ConflictError if expected version does not match actual.

    Parameters
    ----------
    expected:
        The version the client last observed.  ``None`` means skip the check.
    actual:
        The version currently stored in the database.
    current_state:
        A plain dict describing the current server-side state.  Embedded in
        the 409 response body so the client can refresh without an extra GET.
    resource_label:
        Human-readable label for the resource (used in the error message).
    """
    if expected is None:
        return
    if expected != actual:
        raise ConflictError(
            message=(
                f"{resource_label} was modified concurrently. "
                f"Expected version {expected} but found version {actual}. "
                "Refresh and retry."
            ),
            current_state=current_state,
            expected_version=expected,
            actual_version=actual,
        )


# ── Middleware: parse If-Match / X-Row-Version request headers ────────────────

class OptimisticLockMiddleware(BaseHTTPMiddleware):
    """Parse ``If-Match`` and ``X-Row-Version`` request headers and attach the
    parsed integer version to ``request.state.expected_version``.

    This allows endpoint handlers to read ``request.state.expected_version``
    without manually parsing headers.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        expected_version: Optional[int] = None

        # Prefer X-Row-Version; fall back to If-Match (strip surrounding quotes)
        raw = request.headers.get(_VERSION_HEADER) or request.headers.get(_IF_MATCH_HEADER)
        if raw:
            # Strip ETag quotes if present: "3" → 3
            cleaned = raw.strip().strip('"')
            try:
                expected_version = int(cleaned)
            except (ValueError, TypeError):
                expected_version = None

        request.state.expected_version = expected_version
        return await call_next(request)
