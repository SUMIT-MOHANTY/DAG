"""Mocked risk engine adapter with scoring logic."""
import random
from typing import Any, Optional

from .base import BaseRiskEngineAdapter

# ── Risk factor definitions ───────────────────────────────────────────────────

_RISK_FACTORS = {
    "guest": [
        {"factor": "unverified_identity", "weight": 0.35, "description": "Guest identity not verified"},
        {"factor": "payment_dispute_history", "weight": 0.25, "description": "Prior payment disputes on record"},
        {"factor": "age_restriction_flag", "weight": 0.30, "description": "Age verification pending or failed"},
        {"factor": "new_account", "weight": 0.10, "description": "Account created within last 90 days"},
    ],
    "booking": [
        {"factor": "last_minute_booking", "weight": 0.20, "description": "Booking made within 24 hours of check-in"},
        {"factor": "high_value_transaction", "weight": 0.15, "description": "Transaction value exceeds $5,000"},
        {"factor": "multiple_room_types", "weight": 0.10, "description": "Booking spans multiple restricted room types"},
        {"factor": "adults_only_property", "weight": 0.40, "description": "Property has adults-only restriction"},
        {"factor": "unverified_guest_adults_only", "weight": 0.50, "description": "Unverified guest at adults-only property"},
    ],
    "property": [
        {"factor": "high_risk_jurisdiction", "weight": 0.20, "description": "Property in high-risk regulatory jurisdiction"},
        {"factor": "casino_amenity", "weight": 0.25, "description": "Property includes casino facilities"},
        {"factor": "age_restricted_amenities", "weight": 0.30, "description": "Property has age-restricted amenities"},
    ],
}

# Deterministic risk scores keyed by reservation ID for consistency
_RESERVATION_RISK_SCORES: dict[str, float] = {
    "res-001": 0.72,
    "res-002": 0.18,
    "res-003": 0.45,
    "res-004": 0.88,
    "res-005": 0.31,
}

_RESTRICTION_MATCH_SCORES: dict[str, float] = {
    "Adult-Only Resort Policy": 0.95,
    "High-Risk Booking Flag": 0.82,
    "Minimum Age Verification": 0.78,
    "Casino Access Restriction": 0.91,
    "Payment Dispute Hold": 0.65,
}


class MockRiskEngineAdapter(BaseRiskEngineAdapter):
    """In-memory mock implementation of the risk scoring engine."""

    async def score_booking(
        self,
        reservation_id: str,
        guest_id: str,
        property_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        # Use deterministic score if available, otherwise generate pseudo-random
        base_score = _RESERVATION_RISK_SCORES.get(reservation_id, 0.40)

        # Adjust based on context hints
        if context:
            if context.get("adults_only_property") and not context.get("age_verified"):
                base_score = min(1.0, base_score + 0.20)
            if context.get("payment_dispute"):
                base_score = min(1.0, base_score + 0.15)

        risk_level = self._score_to_level(base_score)
        active_factors = self._get_active_factors(base_score, context or {})

        return {
            "reservation_id": reservation_id,
            "guest_id": guest_id,
            "property_id": property_id,
            "risk_score": round(base_score, 4),
            "risk_level": risk_level,
            "confidence": round(0.85 + (base_score * 0.10), 4),
            "active_factors": active_factors,
            "recommendation": self._get_recommendation(risk_level),
            "requires_human_review": base_score >= 0.70,
        }

    async def score_restriction_match(
        self,
        restriction_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        restriction_name = context.get("restriction_name", "")
        base_score = _RESTRICTION_MATCH_SCORES.get(restriction_name, 0.55)

        return {
            "restriction_id": restriction_id,
            "match_score": round(base_score, 4),
            "confidence": round(min(0.99, base_score + 0.05), 4),
            "matched_conditions": context.get("conditions", []),
            "requires_approval": base_score < 0.70 or context.get("risk_level", 1) >= 4,
        }

    async def get_risk_factors(
        self, entity_type: str, entity_id: str
    ) -> list[dict[str, Any]]:
        factors = _RISK_FACTORS.get(entity_type, _RISK_FACTORS["guest"])
        # Return a subset based on entity_id hash for determinism
        seed = sum(ord(c) for c in entity_id)
        count = (seed % 3) + 1
        return factors[:count]

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.80:
            return "critical"
        if score >= 0.60:
            return "high"
        if score >= 0.40:
            return "medium"
        return "low"

    @staticmethod
    def _get_recommendation(risk_level: str) -> str:
        recommendations = {
            "critical": "Block booking and escalate to compliance team immediately",
            "high": "Route to human review queue before confirming",
            "medium": "Flag for secondary review; proceed with caution",
            "low": "Auto-approve with standard monitoring",
        }
        return recommendations.get(risk_level, "Manual review recommended")

    @staticmethod
    def _get_active_factors(score: float, context: dict[str, Any]) -> list[str]:
        factors = []
        if score >= 0.70:
            factors.append("high_risk_score")
        if context.get("adults_only_property"):
            factors.append("adults_only_property")
        if not context.get("age_verified"):
            factors.append("age_verification_pending")
        if context.get("payment_dispute"):
            factors.append("payment_dispute_history")
        return factors
