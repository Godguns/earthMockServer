from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaUpsertRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    archetype: str | None = Field(default=None, max_length=100)
    world_context: str | None = None
    backstory: str | None = None
    system_prompt: str | None = None
    communication_style: str | None = None
    emotional_traits: list[str] = Field(default_factory=list)
    favorite_topics: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    relationship_goals: list[str] = Field(default_factory=list)
    raw_settings: dict = Field(default_factory=dict)
    npc_push_enabled: bool = True
    npc_push_frequency_minutes: int = Field(default=120, ge=15, le=1440)


class FrontendPersonaProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    profileVersion: int = 1
    boundAt: datetime | str | None = None
    identity: dict = Field(default_factory=dict)
    anchors: dict = Field(default_factory=dict)
    saveModel: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    signals: dict = Field(default_factory=dict)
    rawAnswers: dict = Field(default_factory=dict)


class PersonaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str | None
    archetype: str | None
    world_context: str | None
    backstory: str | None
    system_prompt: str | None
    communication_style: str | None
    emotional_traits: list[str]
    favorite_topics: list[str]
    boundaries: list[str]
    relationship_goals: list[str]
    raw_settings: dict
    npc_push_enabled: bool
    npc_push_frequency_minutes: int
    next_npc_push_at: datetime | None
    created_at: datetime
    updated_at: datetime
