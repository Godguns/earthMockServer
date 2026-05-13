from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class NpcConversationSession(Base, TimestampMixin):
    __tablename__ = "npc_conversation_sessions"
    __table_args__ = (UniqueConstraint("user_id", "npc_key", name="uq_user_npc_session"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    npc_key: Mapped[str] = mapped_column(String(80), index=True)
    conversation_key: Mapped[str] = mapped_column(String(120), index=True)
    dify_conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dify_user: Mapped[str] = mapped_column(String(120), index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_player_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_npc_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    user = relationship("User", back_populates="npc_sessions")
