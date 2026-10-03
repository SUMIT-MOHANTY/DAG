"""Pydantic schemas for Policy request/response models."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Shared / base
# ---------------------------------------------------------------------------

class PolicyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., min_length=1, max_length=50)
    document_url: Optional[str] = Field(None, max_length=1024)
    description: Optional[str] = None
    effective_from: datetime = Field(..., description="Policy validity start (UTC)")
    effective_to: Optional[datetime] = Field(None, description="Policy validity end (UTC)")

    @model_validator(mode="after")
    def validate_temporal_range(self) -> "PolicyBase":
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PolicyCreate(PolicyBase):
    """Payload for POST /api/v1/policies."""
    pass


class PolicyUpdate(BaseModel):
    """Payload for PATCH /api/v1/policies/{id}."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None, min_length=1, max_length=50)
    document_url: Optional[str] = Field(None, max_length=1024)
    description: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Booking context for policy evaluation
# ---------------------------------------------------------------------------

class BookingContext(BaseModel):
    """Context passed to policy evaluation engine."""
    booking_id: Optional[str] = None
    traveler_id: Optional[str] = None
    origin: Optional[str] = Field(None, description="IATA origin code")
    destination: Optional[str] = Field(None, description="IATA destination code")
    travel_date: Optional[datetime] = None
    cabin_class: Optional[str] = None
    fare_basis: Optional[str] = None
    passenger_type: Optional[str] = None
    extra_attributes: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Arbitrary key-value pairs for rule matching",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class RestrictionRef(BaseModel):
    """Lightweight restriction reference embedded in policy responses."""
    id: str
    name: str
    rule_type: str
    risk_level: int
    is_active: bool

    model_config = {"from_attributes": True}


class PolicyResponse(PolicyBase):
    """Full policy record returned by the API."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    restrictions: List[RestrictionRef] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PolicyListItem(BaseModel):
    """Compact policy record used in list responses."""
    id: str
    name: str
    version: str
    is_active: bool
    effective_from: datetime
    effective_to: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evaluation response
# ---------------------------------------------------------------------------

class ApplicableRestriction(BaseModel):
    restriction_id: str
    restriction_name: str
    rule_type: str
    risk_score: float = Field(..., ge=0.0, le=10.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    triggered_by: Optional[str] = Field(None, description="Rule or condition that triggered this")
    chained_from: Optional[str] = Field(None, description="Parent restriction ID if chained")


class PolicyEvaluationResponse(BaseModel):
    policy_id: str
    policy_name: str
    policy_version: str
    booking_context: BookingContext
    applicable_restrictions: List[ApplicableRestriction]
    overall_risk_score: float = Field(..., ge=0.0, le=10.0)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    evaluated_at: datetime
    recommendation: str = Field(..., description="ALLOW | REVIEW | BLOCK")


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class PolicyCursorPage(BaseModel):
    items: List[PolicyListItem]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    total_count: Optional[int] = None
    page_size: int
