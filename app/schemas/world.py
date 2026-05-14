from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MoneyState(BaseModel):
    balance: int
    income_monthly: int
    expense_monthly: int
    pressure: float


class HealthState(BaseModel):
    energy: float
    sleep: float
    body: float


class MoodState(BaseModel):
    stability: float
    anxiety: float
    loneliness: float


class RelationState(BaseModel):
    mother: float
    friends: float
    work: float
    institution: float


class TimeState(BaseModel):
    day_label: str
    deadline_label: str
    phase_key: str


class WorldEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_key: str
    tone: str
    title: str
    subtitle: str
    source: str
    priority: str
    due_in: str
    consequence: str
    payload: dict
    status: str
    expires_at: datetime | None
    created_at: datetime


class WorldStateRead(BaseModel):
    money: MoneyState
    health: HealthState
    mood: MoodState
    relations: RelationState
    time: TimeState
    events: list[WorldEventRead] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    journal: list[dict] = Field(default_factory=list)


class WorldActionRequest(BaseModel):
    action_key: str = Field(min_length=1, max_length=80)
