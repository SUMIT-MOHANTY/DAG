"""Custom application exceptions and FastAPI exception handlers.

Includes ConflictError with full current-state payload for optimistic-locking
409 responses (second exception path — concurrent modification scenario).
"""
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ── Domain exceptions ─────────────────────────────────────────────────────────

class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: Any = None) -> None:
        msg = f"{resource} not found"
        if resource_id:
            msg = f"{resource} with id '{resource_id}' not found"
        super().__init__(msg, status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(AppException):
    """Business rule validation failure."""

    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class AuthenticationError(AppException):
    """Authentication failure."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(AppException):
    """Authorization / permission failure."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(AppException):
    """Optimistic-locking / concurrent-modification conflict (HTTP 409).

    Carries the *current* server-side state so the client can perform a
    client-side merge without an extra round-trip.

    Second exception path scenario
    --------------------------------
    Manager A loads AR-001 at version=3.
    Manager B loads AR-001 at version=3.
    Manager B approves  → version bumped to 4, status=approved.
    Manager A rejects   → sends If-Match: 3.
    Server detects mismatch (DB version=4 ≠ client version=3).
    Server raises ConflictError with current_state={version:4, status:approved, …}.
    Client receives HTTP 409 + current_state and can refresh / re-evaluate.
    """

    def __init__(
        self,
        message: str,
        current_state: Optional[dict[str, Any]] = None,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
    ) -> None:
        detail: dict[str, Any] = {
            "conflict_type": "optimistic_lock_failure",
        }
        if expected_version is not None:
            detail["expected_version"] = expected_version
        if actual_version is not None:
            detail["actual_version"] = actual_version
        if current_state is not None:
            detail["current_state"] = current_state
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, detail=detail)


class StateMachineError(AppException):
    """Invalid state transition attempt."""

    def __init__(
        self,
        resource: str,
        from_state: str,
        to_state: str,
        allowed_transitions: Optional[list[str]] = None,
    ) -> None:
        msg = (
            f"Invalid transition for {resource}: '{from_state}' → '{to_state}' is not permitted."
        )
        detail: dict[str, Any] = {
            "from_state": from_state,
            "to_state": to_state,
        }
        if allowed_transitions is not None:
            detail["allowed_transitions"] = allowed_transitions
        super().__init__(msg, status_code=status.HTTP_409_CONFLICT, detail=detail)


class ExternalServiceError(AppException):
    """Downstream adapter / external service failure."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            f"External service '{service}' error: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


# ── Exception handlers ────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        content: dict[str, Any] = {"error": exc.message}
        if exc.detail is not None:
            content["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "The requested resource was not found"},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Any) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal server error occurred"},
        )
