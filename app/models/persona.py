from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class PersonaProfile(Base, TimestampMixin):
    __tablename__ = "persona_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    archetype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    world_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotional_traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    favorite_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    boundaries: Mapped[list[str]] = mapped_column(JSON, default=list)
    relationship_goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    npc_push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    npc_push_frequency_minutes: Mapped[int] = mapped_column(Integer, default=120)
    next_npc_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="persona_profile")

