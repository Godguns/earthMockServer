from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    persona_profile = relationship(
        "PersonaProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    message_events = relationship(
        "MessageEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )

