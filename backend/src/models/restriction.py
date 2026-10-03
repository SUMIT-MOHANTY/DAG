"""Restriction model for booking rules and compliance constraints."""
from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TemporalMixin


class Restriction(TemporalMixin, BaseModel):
    """Booking restriction with rule parameters and risk classification."""

    __tablename__ = "restrictions"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rule_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    parameters: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    risk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    source_policy_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    source_policy = relationship("Policy", back_populates="restrictions", lazy="select")
    evidence_items = relationship("Evidence", back_populates="restriction", lazy="select")
    approval_requests = relationship(
        "ApprovalRequest",
        back_populates="restriction_query",
        foreign_keys="ApprovalRequest.restriction_query_id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Restriction id={self.id} name={self.name} risk_level={self.risk_level}>"
