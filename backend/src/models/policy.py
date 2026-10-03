"""Policy model for compliance documents."""
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TemporalMixin


class Policy(TemporalMixin, BaseModel):
    """Compliance policy document with versioning and temporal validity."""

    __tablename__ = "policies"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    document_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    restrictions = relationship("Restriction", back_populates="source_policy", lazy="select")

    def __repr__(self) -> str:
        return f"<Policy id={self.id} name={self.name} version={self.version}>"
