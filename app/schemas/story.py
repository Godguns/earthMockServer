from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StoryChoice(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    description: str | None = None
    next_scene_key: str | None = None
    effect_key: str | None = None
    world_effects: dict | None = None


class StoryLine(BaseModel):
    speaker: str
    text: str
    emotion: str | None = None


class StorySceneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    arc_key: str
    current_scene_key: str | None
    branch_key: str | None
    flags: dict
    completed_at: datetime | None


class StoryBranchOption(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    description: str | None = None
    start_scene_key: str | None = None
    recommended: bool = False


class StoryScenePayload(BaseModel):
    key: str
    title: str
    scene_type: str
    lines: list[StoryLine] = Field(default_factory=list)
    choices: list[StoryChoice] = Field(default_factory=list)
    background: str | None = None
    music_cue: str | None = None
    enter_effect: str | None = None


class StoryStateRead(BaseModel):
    progress: StorySceneRead
    branches: list[StoryBranchOption] = Field(default_factory=list)
    scene: StoryScenePayload | None = None
    selected_choice: StoryChoice | None = None


class StoryStartRequest(BaseModel):
    branch_key: str = Field(min_length=1, max_length=64)


class StoryChoiceRequest(BaseModel):
    choice_key: str = Field(min_length=1, max_length=64)
