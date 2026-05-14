from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class StoryArc(Base, TimestampMixin):
    __tablename__ = "story_arcs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    branching_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    entry_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(default=True)

    scenes = relationship("StoryScene", back_populates="arc", cascade="all, delete-orphan")


class StoryScene(Base, TimestampMixin):
    __tablename__ = "story_scenes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    arc_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("story_arcs.id"), index=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(120))
    scene_type: Mapped[str] = mapped_column(String(32), default="dialogue")
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    choice_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    next_scene_map: Mapped[dict] = mapped_column(JSON, default=dict)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    arc = relationship("StoryArc", back_populates="scenes")


class StoryProgress(Base, TimestampMixin):
    __tablename__ = "story_progress"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, index=True)
    arc_key: Mapped[str] = mapped_column(String(64), index=True)
    current_scene_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

