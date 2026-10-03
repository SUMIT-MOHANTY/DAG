"""FastAPI application entry point with CORS, middleware, and v1 router."""
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.src.config.settings import settings
from backend.src.config.logging import configure_logging, get_logger
from backend.src.core.exceptions import register_exception_handlers

# Configure logging before anything else
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting Restriction Intelligence API", version=settings.app_version)
    # Import here to avoid circular imports at module load time
    from backend.src.config.database import engine
    from backend.src.models.base import Base  # noqa: F401
    import backend.src.models  # noqa: F401 — ensure all models are registered

    async with engine.begin() as conn:
        # In development, create tables if they don't exist
        if settings.environment in ("development", "test"):
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ensured")

    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")
    await engine.dispose()
    logger.info("Database connections closed")


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered restriction intelligence and compliance management API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Request ID + structured logging middleware ────────────────────────────
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:  # type: ignore[type-arg]
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all API routers under /api/v1."""
    # Import routers lazily to avoid circular imports
    try:
        from backend.src.api.v1 import router as v1_router
        app.include_router(v1_router, prefix="/api/v1")
    except ImportError:
        # Routers not yet implemented — skip gracefully
        logger.warning("v1 router not found, skipping router registration")


# ── Health check (always available, no auth) ──────────────────────────────────
app = create_app()


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Liveness probe — returns service status and version."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    """Root endpoint — API discovery."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "disabled",
        "health": "/health",
    }
