from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PlayerWorldState(Base, TimestampMixin):
    __tablename__ = "player_world_states"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, index=True)

    money_balance: Mapped[int] = mapped_column(Integer, default=3860)
    money_income_monthly: Mapped[int] = mapped_column(Integer, default=6200)
    money_expense_monthly: Mapped[int] = mapped_column(Integer, default=2540)
    money_pressure: Mapped[float] = mapped_column(default=0.38)

    health_energy: Mapped[float] = mapped_column(default=0.72)
    health_sleep: Mapped[float] = mapped_column(default=0.64)
    health_body: Mapped[float] = mapped_column(default=0.81)

    mood_stability: Mapped[float] = mapped_column(default=0.58)
    mood_anxiety: Mapped[float] = mapped_column(default=0.42)
    mood_loneliness: Mapped[float] = mapped_column(default=0.27)

    relation_mother: Mapped[float] = mapped_column(default=0.74)
    relation_friends: Mapped[float] = mapped_column(default=0.55)
    relation_work: Mapped[float] = mapped_column(default=0.62)
    relation_institution: Mapped[float] = mapped_column(default=0.48)

    day_label: Mapped[str] = mapped_column(String(40), default="周三 晚上")
    deadline_label: Mapped[str] = mapped_column(String(80), default="房租 3 天后到期")
    phase_key: Mapped[str] = mapped_column(String(40), default="life_bootstrap")
    tags: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerWorldEvent(Base, TimestampMixin):
    __tablename__ = "player_world_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(80), index=True)
    tone: Mapped[str] = mapped_column(String(24), default="info")
    title: Mapped[str] = mapped_column(String(120))
    subtitle: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="系统")
    priority: Mapped[str] = mapped_column(String(24), default="medium")
    due_in: Mapped[str] = mapped_column(String(40), default="现在")
    consequence: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
