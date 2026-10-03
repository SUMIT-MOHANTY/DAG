"""ApprovalRequest model for human-in-the-loop review queue."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class ApprovalRequest(BaseModel):
    """Human review request for high-risk or low-confidence restriction decisions."""

    __tablename__ = "approval_requests"

    restriction_query_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("restrictions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    queue_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="low_confidence",
    )
    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_rationale: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    context_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    # Relationships
    restriction_query = relationship(
        "Restriction",
        back_populates="approval_requests",
        foreign_keys=[restriction_query_id],
        lazy="select",
    )
    assignee = relationship(
        "User",
        back_populates="assigned_approvals",
        foreign_keys=[assigned_to],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<ApprovalRequest id={self.id} status={self.status} priority={self.priority}>"
