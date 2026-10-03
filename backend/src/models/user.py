"""User model for authentication and authorization."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class User(BaseModel):
    """User entity supporting admin and operator roles."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="operator",
        server_default="operator",
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user", lazy="select")
    conversations = relationship("Conversation", back_populates="user", lazy="select")
    assigned_approvals = relationship(
        "ApprovalRequest",
        back_populates="assignee",
        foreign_keys="ApprovalRequest.assigned_to",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
