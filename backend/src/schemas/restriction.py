"""Pydantic schemas for Restriction request/response models."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared / base
# ---------------------------------------------------------------------------

class RestrictionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Restriction name")
    description: Optional[str] = Field(None, description="Human-readable description")
    rule_type: str = Field(..., min_length=1, max_length=100, description="Rule category")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Rule parameters as JSON")
    risk_level: int = Field(1, ge=1, le=10, description="Risk level 1 (low) to 10 (critical)")
    source_policy_id: Optional[str] = Field(None, description="Parent policy UUID")
    effective_from: datetime = Field(..., description="Start of temporal validity (UTC)")
    effective_to: Optional[datetime] = Field(None, description="End of temporal validity (UTC)")

    @model_validator(mode="after")
    def validate_temporal_range(self) -> "RestrictionBase":
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RestrictionCreate(RestrictionBase):
    """Payload for POST /api/v1/restrictions."""
    pass


class RestrictionUpdate(BaseModel):
    """Payload for PATCH /api/v1/restrictions/{id} — all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    rule_type: Optional[str] = Field(None, min_length=1, max_length=100)
    parameters: Optional[Dict[str, Any]] = None
    risk_level: Optional[int] = Field(None, ge=1, le=10)
    source_policy_id: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class EvidenceSummary(BaseModel):
    """Lightweight evidence summary embedded in restriction responses."""
    id: str
    source_table: str
    source_record_id: str
    confidence_score: Optional[float]
    collected_at: datetime

    model_config = {"from_attributes": True}


class RestrictionResponse(RestrictionBase):
    """Full restriction record returned by the API."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    evidence_items: List[EvidenceSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RestrictionListItem(BaseModel):
    """Compact restriction record used in list responses."""
    id: str
    name: str
    rule_type: str
    risk_level: int
    is_active: bool
    effective_from: datetime
    effective_to: Optional[datetime]
    source_policy_id: Optional[str]
    created_at: datetime
    relevance_score: Optional[float] = Field(None, description="Fuzzy search relevance (0-1)")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class CursorPage(BaseModel):
    """Generic cursor-based pagination envelope."""
    items: List[RestrictionListItem]
    next_cursor: Optional[str] = Field(None, description="Opaque cursor for next page")
    prev_cursor: Optional[str] = Field(None, description="Opaque cursor for previous page")
    total_count: Optional[int] = Field(None, description="Total matching records (may be None for perf)")
    page_size: int


# ---------------------------------------------------------------------------
# Filter / query params helper (used by service layer)
# ---------------------------------------------------------------------------

class RestrictionFilters(BaseModel):
    risk_level: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None
    effective_from_gte: Optional[datetime] = None
    effective_from_lte: Optional[datetime] = None
    policy_id: Optional[str] = None
    search: Optional[str] = Field(None, max_length=200, description="Fuzzy search term")
    cursor: Optional[str] = None
    page_size: int = Field(20, ge=1, le=100)
