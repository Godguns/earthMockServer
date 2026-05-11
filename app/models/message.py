from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class MessageChannel(StrEnum):
    notification = "notification"
    chat = "chat"


class MessageSourceType(StrEnum):
    system = "system"
    npc = "npc"
    event = "event"
    admin = "admin"


class MessageTriggerType(StrEnum):
    random = "random"
    event = "event"
    manual = "manual"
    scheduled = "scheduled"


class MessageDeliveryStatus(StrEnum):
    pending = "pending"
    delivered = "delivered"
    read = "read"


class MessageEvent(Base, TimestampMixin):
    __tablename__ = "message_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), index=True)
    source_type: Mapped[MessageSourceType] = mapped_column(Enum(MessageSourceType), index=True)
    trigger_type: Mapped[MessageTriggerType] = mapped_column(Enum(MessageTriggerType), index=True)
    delivery_status: Mapped[MessageDeliveryStatus] = mapped_column(
        Enum(MessageDeliveryStatus),
        default=MessageDeliveryStatus.delivered,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    sender_name: Mapped[str] = mapped_column(String(100), default="System")
    conversation_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="message_events")

