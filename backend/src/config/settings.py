"""Application settings with dynamic threshold reload via cache TTL."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Path to the optional runtime threshold override file.
# When present, its values shadow the environment-variable defaults.
_THRESHOLD_OVERRIDE_FILE = Path(
    os.environ.get("THRESHOLD_OVERRIDE_FILE", "threshold_overrides.json")
)

# Cache TTL in seconds — thresholds are re-read from the override file at most
# once per this interval, avoiding file I/O on every request.
_THRESHOLD_CACHE_TTL: float = float(os.environ.get("THRESHOLD_CACHE_TTL", "30"))


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = Field(default="Restriction Intelligence API")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./restriction_intelligence.db"
    )
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_pool_timeout: int = Field(default=30)
    db_echo: bool = Field(default=False)

    # ── Security / JWT ───────────────────────────────────────────────────────
    jwt_secret_key: str = Field(default="change-me-in-production-super-secret-key-32chars")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=7)

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]
    )
    cors_allow_credentials: bool = Field(default=True)

    # ── LLM / AI ─────────────────────────────────────────────────────────────
    llm_api_key: Optional[str] = Field(default=None)
    llm_model: str = Field(default="gpt-4o")
    llm_temperature: float = Field(default=0.0)
    llm_max_tokens: int = Field(default=2048)

    # ── Business Thresholds ───────────────────────────────────────────────────
    risk_threshold: int = Field(default=4, ge=1, le=5)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    auto_approve_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    high_risk_threshold: int = Field(default=4, ge=1, le=5)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json | text

    # ── Threshold validation ──────────────────────────────────────────────────
    @model_validator(mode="after")
    def validate_threshold_combinations(self) -> "Settings":
        """Prevent invalid threshold combinations.

        Rules enforced:
        - high_risk_threshold must be > confidence_threshold * 5  (different scales,
          but high_risk must be at least 1 integer step above the scaled confidence).
        - auto_approve_confidence must be >= confidence_threshold.
        - high_risk_threshold must be <= risk_threshold (high-risk is a sub-band).
        """
        if self.auto_approve_confidence < self.confidence_threshold:
            raise ValueError(
                f"auto_approve_confidence ({self.auto_approve_confidence}) must be "
                f">= confidence_threshold ({self.confidence_threshold})"
            )
        if self.high_risk_threshold > self.risk_threshold:
            raise ValueError(
                f"high_risk_threshold ({self.high_risk_threshold}) must be "
                f"<= risk_threshold ({self.risk_threshold})"
            )
        return self


# ── Singleton + dynamic reload ────────────────────────────────────────────────

class _DynamicSettings:
    """Wrapper around Settings that supports hot-reload of threshold values.

    Threshold overrides are read from a JSON file (path controlled by the
    ``THRESHOLD_OVERRIDE_FILE`` env var).  The file is re-read at most once
    per ``_THRESHOLD_CACHE_TTL`` seconds so there is no per-request I/O.

    Example override file::

        {
            "risk_threshold": 3,
            "confidence_threshold": 0.8,
            "auto_approve_confidence": 0.95,
            "high_risk_threshold": 3
        }
    """

    _THRESHOLD_KEYS = {
        "risk_threshold",
        "confidence_threshold",
        "auto_approve_confidence",
        "high_risk_threshold",
    }

    def __init__(self) -> None:
        self._base = Settings()
        self._overrides: dict[str, Any] = {}
        self._last_loaded: float = 0.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _maybe_reload(self) -> None:
        """Re-read the override file if the cache TTL has expired."""
        now = time.monotonic()
        if now - self._last_loaded < _THRESHOLD_CACHE_TTL:
            return
        self._last_loaded = now
        if not _THRESHOLD_OVERRIDE_FILE.exists():
            self._overrides = {}
            return
        try:
            raw = _THRESHOLD_OVERRIDE_FILE.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
            # Only accept known threshold keys
            filtered = {k: v for k, v in data.items() if k in self._THRESHOLD_KEYS}
            # Validate the merged result before accepting
            merged = self._base.model_dump()
            merged.update(filtered)
            Settings(**merged)  # raises ValueError on invalid combos
            self._overrides = filtered
            logger.debug("Threshold overrides reloaded: %s", filtered)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning("Failed to reload threshold overrides: %s", exc)
            # Keep the previous valid overrides

    # ── Public attribute access ───────────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        self._maybe_reload()
        if name in self._THRESHOLD_KEYS and name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)

    # ── Threshold management API ──────────────────────────────────────────────

    def get_thresholds(self) -> dict[str, Any]:
        """Return current effective threshold values (base + overrides)."""
        self._maybe_reload()
        base = {
            k: getattr(self._base, k) for k in self._THRESHOLD_KEYS
        }
        base.update(self._overrides)
        return base

    def update_thresholds(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Persist new threshold values to the override file and reload.

        Validates the merged result before writing.  Raises ``ValueError`` on
        invalid combinations.

        Returns the new effective thresholds.
        """
        unknown = set(updates) - self._THRESHOLD_KEYS
        if unknown:
            raise ValueError(f"Unknown threshold keys: {unknown}")

        # Merge: base → current overrides → new updates
        merged_overrides = {**self._overrides, **updates}
        merged_full = self._base.model_dump()
        merged_full.update(merged_overrides)
        Settings(**merged_full)  # validate — raises ValueError on bad combos

        # Persist
        _THRESHOLD_OVERRIDE_FILE.write_text(
            json.dumps(merged_overrides, indent=2), encoding="utf-8"
        )
        self._overrides = merged_overrides
        self._last_loaded = time.monotonic()  # reset TTL
        logger.info("Threshold overrides updated: %s", merged_overrides)
        return self.get_thresholds()

    def reset_thresholds(self) -> dict[str, Any]:
        """Remove all overrides and revert to environment-variable defaults."""
        if _THRESHOLD_OVERRIDE_FILE.exists():
            _THRESHOLD_OVERRIDE_FILE.unlink()
        self._overrides = {}
        self._last_loaded = time.monotonic()
        logger.info("Threshold overrides reset to defaults")
        return self.get_thresholds()

    def force_reload(self) -> dict[str, Any]:
        """Force an immediate re-read of the override file, bypassing the TTL."""
        self._last_loaded = 0.0
        self._maybe_reload()
        return self.get_thresholds()


# Singleton instance — import this everywhere
settings = _DynamicSettings()
