from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InternalUserItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    persona_display_name: str | None = None
    persona_city: str | None = None
    has_bound_persona: bool = False
    message_count: int = 0
    unread_message_count: int = 0
    npc_session_count: int = 0
    latest_message_at: datetime | None = None
    latest_npc_message_at: datetime | None = None


class InternalUsersResponse(BaseModel):
    total_users: int
    active_users: int
    bound_persona_users: int
    items: list[InternalUserItem]
