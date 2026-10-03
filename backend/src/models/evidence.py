"""Evidence model for restriction audit lineage, plus hash-chained AuditLog."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, AuditMixin


class Evidence(AuditMixin, Base):
    """Evidence record linking restrictions to source data."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    restriction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("restrictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_table: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source_record_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source_field: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    evidence_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    # Relationships
    restriction = relationship("Restriction", back_populates="evidence_items", lazy="select")

    def __repr__(self) -> str:
        return f"<Evidence id={self.id} restriction_id={self.restriction_id} confidence={self.confidence_score}>"


class HashChainedAuditLog(Base):
    """Tamper-evident, append-only audit log with SHA-256 hash chain.

    Each record stores:
    - ``previous_hash``: SHA-256 of the previous record (or GENESIS for the first).
    - ``current_hash``:  SHA-256 of (previous_hash + canonical payload).
    - ``integrity_verified_at``: last time the chain was verified up to this record.

    The chain is broken if recomputing current_hash from the stored payload
    yields a different value, or if previous_hash does not match the prior
    record's current_hash.
    """

    __tablename__ = "hash_chained_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # ── Event metadata ────────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # ── Hash chain fields ─────────────────────────────────────────────────────
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    previous_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    current_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    integrity_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    actor = relationship("User", lazy="select", foreign_keys=[actor_id])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<HashChainedAuditLog seq={self.sequence_number} "
            f"event={self.event_type} hash={self.current_hash[:8]}...>"
        )
