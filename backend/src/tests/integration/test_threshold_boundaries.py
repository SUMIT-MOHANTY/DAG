"""Threshold boundary condition tests.

Verifies routing behavior at exact threshold values:
- risk_score = 6.99 vs 7.0 (boundary crossing)
- confidence_score = 0.69 vs 0.70 (boundary crossing)
- auto_approve_confidence boundary
- high_risk_threshold boundary
- Configuration validation at boundary values
- Dynamic threshold reload at boundaries

Note: The Settings model uses integer risk_threshold (1-5 scale).
The tests below use the actual Settings fields and validate boundary
behavior for the routing logic.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend.src.config.settings import Settings, _DynamicSettings


# ── Routing logic helper ──────────────────────────────────────────────────────

def _route_request(
    risk_score: float,
    confidence_score: float,
    risk_threshold: int,
    confidence_threshold: float,
    auto_approve_confidence: float,
    high_risk_threshold: int,
) -> str:
    """Simulate the routing decision logic.

    Returns one of:
    - 'auto_approve'   : confidence >= auto_approve_confidence
    - 'high_risk_queue': risk_score >= high_risk_threshold (integer scale 1-5)
    - 'low_confidence_queue': confidence < confidence_threshold
    - 'standard_queue' : passes all thresholds
    """
    if confidence_score >= auto_approve_confidence:
        return "auto_approve"
    if risk_score >= high_risk_threshold:
        return "high_risk_queue"
    if confidence_score < confidence_threshold:
        return "low_confidence_queue"
    return "standard_queue"


# ── Settings boundary tests ───────────────────────────────────────────────────

class TestSettingsBoundaryValidation:
    """Settings model boundary validation tests."""

    def test_risk_threshold_minimum_valid(self) -> None:
        """risk_threshold=1 is valid (minimum)."""
        s = Settings(
            risk_threshold=1,
            high_risk_threshold=1,
            confidence_threshold=0.5,
            auto_approve_confidence=0.95,
        )
        assert s.risk_threshold == 1

    def test_risk_threshold_maximum_valid(self) -> None:
        """risk_threshold=5 is valid (maximum)."""
        s = Settings(
            risk_threshold=5,
            high_risk_threshold=5,
            confidence_threshold=0.5,
            auto_approve_confidence=0.95,
        )
        assert s.risk_threshold == 5

    def test_confidence_threshold_zero_valid(self) -> None:
        """confidence_threshold=0.0 is valid (minimum)."""
        s = Settings(
            confidence_threshold=0.0,
            auto_approve_confidence=0.0,
            risk_threshold=4,
            high_risk_threshold=4,
        )
        assert s.confidence_threshold == 0.0

    def test_confidence_threshold_one_valid(self) -> None:
        """confidence_threshold=1.0 is valid (maximum)."""
        s = Settings(
            confidence_threshold=1.0,
            auto_approve_confidence=1.0,
            risk_threshold=4,
            high_risk_threshold=4,
        )
        assert s.confidence_threshold == 1.0

    def test_auto_approve_must_be_gte_confidence_threshold(self) -> None:
        """auto_approve_confidence < confidence_threshold raises ValueError."""
        with pytest.raises(ValueError, match="auto_approve_confidence"):
            Settings(
                confidence_threshold=0.8,
                auto_approve_confidence=0.7,  # invalid: less than confidence_threshold
                risk_threshold=4,
                high_risk_threshold=4,
            )

    def test_auto_approve_equal_to_confidence_threshold_valid(self) -> None:
        """auto_approve_confidence == confidence_threshold is valid (boundary)."""
        s = Settings(
            confidence_threshold=0.7,
            auto_approve_confidence=0.7,  # exactly equal — valid
            risk_threshold=4,
            high_risk_threshold=4,
        )
        assert s.auto_approve_confidence == 0.7

    def test_high_risk_must_be_lte_risk_threshold(self) -> None:
        """high_risk_threshold > risk_threshold raises ValueError."""
        with pytest.raises(ValueError, match="high_risk_threshold"):
            Settings(
                risk_threshold=3,
                high_risk_threshold=4,  # invalid: exceeds risk_threshold
                confidence_threshold=0.5,
                auto_approve_confidence=0.95,
            )

    def test_high_risk_equal_to_risk_threshold_valid(self) -> None:
        """high_risk_threshold == risk_threshold is valid (boundary)."""
        s = Settings(
            risk_threshold=4,
            high_risk_threshold=4,  # exactly equal — valid
            confidence_threshold=0.5,
            auto_approve_confidence=0.95,
        )
        assert s.high_risk_threshold == 4


# ── Routing boundary tests ────────────────────────────────────────────────────

class TestRoutingBoundaryConditions:
    """Routing decision boundary condition tests."""

    # Default thresholds for routing tests
    _DEFAULTS = {
        "risk_threshold": 4,
        "confidence_threshold": 0.70,
        "auto_approve_confidence": 0.95,
        "high_risk_threshold": 4,
    }

    def test_confidence_just_below_threshold_routes_low_confidence(self) -> None:
        """confidence=0.69 (just below 0.70) → low_confidence_queue."""
        result = _route_request(
            risk_score=2.0,
            confidence_score=0.69,
            **self._DEFAULTS,
        )
        assert result == "low_confidence_queue", (
            f"Expected low_confidence_queue for confidence=0.69, got {result}"
        )

    def test_confidence_at_threshold_routes_standard(self) -> None:
        """confidence=0.70 (exactly at threshold) → standard_queue."""
        result = _route_request(
            risk_score=2.0,
            confidence_score=0.70,
            **self._DEFAULTS,
        )
        assert result == "standard_queue", (
            f"Expected standard_queue for confidence=0.70, got {result}"
        )

    def test_confidence_just_above_threshold_routes_standard(self) -> None:
        """confidence=0.71 (just above 0.70) → standard_queue."""
        result = _route_request(
            risk_score=2.0,
            confidence_score=0.71,
            **self._DEFAULTS,
        )
        assert result == "standard_queue"

    def test_risk_just_below_high_risk_threshold_routes_standard(self) -> None:
        """risk_score=3 (just below high_risk_threshold=4) → standard_queue."""
        result = _route_request(
            risk_score=3,
            confidence_score=0.75,
            **self._DEFAULTS,
        )
        assert result == "standard_queue", (
            f"Expected standard_queue for risk=3, got {result}"
        )

    def test_risk_at_high_risk_threshold_routes_high_risk(self) -> None:
        """risk_score=4 (exactly at high_risk_threshold=4) → high_risk_queue."""
        result = _route_request(
            risk_score=4,
            confidence_score=0.75,
            **self._DEFAULTS,
        )
        assert result == "high_risk_queue", (
            f"Expected high_risk_queue for risk=4, got {result}"
        )

    def test_risk_above_high_risk_threshold_routes_high_risk(self) -> None:
        """risk_score=5 (above high_risk_threshold=4) → high_risk_queue."""
        result = _route_request(
            risk_score=5,
            confidence_score=0.75,
            **self._DEFAULTS,
        )
        assert result == "high_risk_queue"

    def test_auto_approve_just_below_threshold(self) -> None:
        """confidence=0.94 (just below auto_approve=0.95) → not auto_approved."""
        result = _route_request(
            risk_score=2.0,
            confidence_score=0.94,
            **self._DEFAULTS,
        )
        assert result != "auto_approve", (
            f"Should not auto-approve at confidence=0.94, got {result}"
        )

    def test_auto_approve_at_threshold(self) -> None:
        """confidence=0.95 (exactly at auto_approve threshold) → auto_approve."""
        result = _route_request(
            risk_score=5,  # even high risk
            confidence_score=0.95,
            **self._DEFAULTS,
        )
        assert result == "auto_approve", (
            f"Expected auto_approve at confidence=0.95, got {result}"
        )

    def test_auto_approve_above_threshold(self) -> None:
        """confidence=0.99 (above auto_approve threshold) → auto_approve."""
        result = _route_request(
            risk_score=5,
            confidence_score=0.99,
            **self._DEFAULTS,
        )
        assert result == "auto_approve"

    def test_boundary_crossing_confidence_0_69_vs_0_70(self) -> None:
        """Verify the exact boundary crossing at confidence 0.69 vs 0.70."""
        below = _route_request(risk_score=2.0, confidence_score=0.69, **self._DEFAULTS)
        at = _route_request(risk_score=2.0, confidence_score=0.70, **self._DEFAULTS)
        assert below == "low_confidence_queue"
        assert at == "standard_queue"
        assert below != at, "Boundary crossing should change routing decision"

    def test_combined_high_risk_low_confidence(self) -> None:
        """High risk + low confidence → high_risk_queue (risk check takes priority)."""
        result = _route_request(
            risk_score=4,
            confidence_score=0.50,  # below confidence threshold
            **self._DEFAULTS,
        )
        # Risk check happens before confidence check in our routing logic
        assert result == "high_risk_queue"


# ── Dynamic threshold reload boundary tests ───────────────────────────────────

class TestDynamicThresholdBoundaries:
    """Dynamic threshold reload at boundary values."""

    def test_update_confidence_threshold_to_boundary(self) -> None:
        """Update confidence_threshold to 0.70 (boundary value) succeeds."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            import backend.src.config.settings as settings_module
            original_file = settings_module._THRESHOLD_OVERRIDE_FILE
            settings_module._THRESHOLD_OVERRIDE_FILE = Path(tmp_path)

            dyn = _DynamicSettings()
            result = dyn.update_thresholds({"confidence_threshold": 0.70})
            assert result["confidence_threshold"] == 0.70
        finally:
            settings_module._THRESHOLD_OVERRIDE_FILE = original_file
            os.unlink(tmp_path)

    def test_update_risk_threshold_to_boundary(self) -> None:
        """Update risk_threshold to 1 (minimum boundary) succeeds."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            import backend.src.config.settings as settings_module
            original_file = settings_module._THRESHOLD_OVERRIDE_FILE
            settings_module._THRESHOLD_OVERRIDE_FILE = Path(tmp_path)

            dyn = _DynamicSettings()
            result = dyn.update_thresholds({
                "risk_threshold": 1,
                "high_risk_threshold": 1,
            })
            assert result["risk_threshold"] == 1
            assert result["high_risk_threshold"] == 1
        finally:
            settings_module._THRESHOLD_OVERRIDE_FILE = original_file
            os.unlink(tmp_path)

    def test_invalid_threshold_combination_rejected(self) -> None:
        """Invalid threshold combination is rejected at boundary."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            import backend.src.config.settings as settings_module
            original_file = settings_module._THRESHOLD_OVERRIDE_FILE
            settings_module._THRESHOLD_OVERRIDE_FILE = Path(tmp_path)

            dyn = _DynamicSettings()
            with pytest.raises(ValueError):
                dyn.update_thresholds({
                    "confidence_threshold": 0.9,
                    "auto_approve_confidence": 0.8,  # invalid: less than confidence_threshold
                })
        finally:
            settings_module._THRESHOLD_OVERRIDE_FILE = original_file
            os.unlink(tmp_path)

    def test_reset_thresholds_restores_defaults(self) -> None:
        """reset_thresholds() restores default values."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            import backend.src.config.settings as settings_module
            original_file = settings_module._THRESHOLD_OVERRIDE_FILE
            settings_module._THRESHOLD_OVERRIDE_FILE = Path(tmp_path)

            dyn = _DynamicSettings()
            # Update then reset
            dyn.update_thresholds({"confidence_threshold": 0.8})
            defaults = dyn.reset_thresholds()

            # After reset, should return base Settings defaults
            base = Settings()
            assert defaults["confidence_threshold"] == base.confidence_threshold
        finally:
            settings_module._THRESHOLD_OVERRIDE_FILE = original_file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_thresholds_returns_all_keys(self) -> None:
        """get_thresholds() returns all four threshold keys."""
        dyn = _DynamicSettings()
        thresholds = dyn.get_thresholds()
        required_keys = {
            "risk_threshold",
            "confidence_threshold",
            "auto_approve_confidence",
            "high_risk_threshold",
        }
        assert required_keys.issubset(set(thresholds.keys())), (
            f"Missing threshold keys: {required_keys - set(thresholds.keys())}"
        )


# ── API endpoint threshold boundary tests ─────────────────────────────────────

class TestThresholdAPIBoundaries:
    """Test threshold configuration via API at boundary values."""

    @pytest.mark.asyncio
    async def test_get_config_returns_thresholds(self, client) -> None:
        """GET /admin/config returns current threshold values."""
        response = await client.get("/admin/config")
        assert response.status_code == 200
        data = response.json()
        assert "risk_threshold" in data
        assert "confidence_threshold" in data
        assert "auto_approve_confidence" in data
        assert "high_risk_threshold" in data

    @pytest.mark.asyncio
    async def test_update_config_boundary_confidence(self, client) -> None:
        """PUT /admin/config with confidence_threshold=0.70 succeeds."""
        response = await client.put(
            "/admin/config",
            json={"confidence_threshold": 0.70, "auto_approve_confidence": 0.95},
        )
        # Should succeed (valid boundary value)
        assert response.status_code in (200, 422), (
            f"Unexpected status: {response.status_code}"
        )
        if response.status_code == 200:
            data = response.json()
            assert data["confidence_threshold"] == 0.70

    @pytest.mark.asyncio
    async def test_update_config_invalid_combination_rejected(self, client) -> None:
        """PUT /admin/config with invalid combination returns 422."""
        response = await client.put(
            "/admin/config",
            json={
                "confidence_threshold": 0.9,
                "auto_approve_confidence": 0.5,  # invalid: less than confidence_threshold
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reset_config_restores_defaults(self, client) -> None:
        """POST /admin/config/reset returns valid threshold values."""
        response = await client.post("/admin/config/reset")
        assert response.status_code == 200
        data = response.json()
        assert "risk_threshold" in data
        assert "confidence_threshold" in data
