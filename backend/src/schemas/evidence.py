"""Pydantic schemas for Evidence request/response models."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EvidenceCreate(BaseModel):
    """Payload for POST /api/v1/evidence."""
    restriction_id: str = Field(..., description="UUID of the linked restriction")
    source_table: str = Field(..., min_length=1, max_length=255)
    source_record_id: str = Field(..., min_length=1, max_length=255)
    source_field: str = Field(..., min_length=1, max_length=255)
    evidence_value: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    collected_at: Optional[datetime] = Field(
        None,
        description="Timestamp of collection; defaults to now if omitted",
    )


class EvidenceFilter(BaseModel):
    """Query parameters for GET /api/v1/evidence."""
    restriction_id: Optional[str] = None
    source_table: Optional[str] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    cursor: Optional[str] = None
    page_size: int = Field(20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class EvidenceResponse(BaseModel):
    """Full evidence record returned by the API."""
    id: str
    restriction_id: str
    source_table: str
    source_record_id: str
    source_field: str
    evidence_value: Optional[str]
    confidence_score: Optional[float]
    collected_at: datetime

    model_config = {"from_attributes": True}


class EvidenceChainValidation(BaseModel):
    """Result of validate_evidence_chain."""
    restriction_id: str
    is_valid: bool
    total_evidence_count: int
    avg_confidence: Optional[float]
    missing_sources: List[str] = Field(default_factory=list)
    integrity_issues: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class EvidenceCursorPage(BaseModel):
    items: List[EvidenceResponse]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    total_count: Optional[int] = None
    page_size: int
