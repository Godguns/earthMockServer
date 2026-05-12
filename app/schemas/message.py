from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import (
    MessageChannel,
    MessageDeliveryStatus,
    MessageSourceType,
    MessageTriggerType,
)


class EventTriggerRequest(BaseModel):
    trigger_name: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1)
    sender_name: str = Field(default="System", max_length=100)
    conversation_key: str | None = Field(default=None, max_length=120)
    source_type: MessageSourceType = MessageSourceType.event
    channel_targets: list[MessageChannel] = Field(
        default_factory=lambda: [MessageChannel.notification, MessageChannel.chat]
    )
    scheduled_for: datetime | None = None
    payload: dict = Field(default_factory=dict)


class PlayerReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    conversation_key: str | None = Field(default=None, max_length=120)
    sender_name: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    client_message_id: str | None = Field(default=None, max_length=160)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    channel: MessageChannel
    source_type: MessageSourceType
    trigger_type: MessageTriggerType
    delivery_status: MessageDeliveryStatus
    title: str | None
    content: str
    sender_name: str
    conversation_key: str | None
    payload: dict
    scheduled_for: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageRead]
    server_time: datetime | None = None


class RandomMessageResponse(BaseModel):
    created: list[MessageRead]
