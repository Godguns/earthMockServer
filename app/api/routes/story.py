from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.story import (
    StoryChoiceRequest,
    StorySceneRead,
    StoryStartRequest,
    StoryStateRead,
)
from app.services.persona_service import get_or_create_persona
from app.services.story_service import (
    advance_story_choice,
    build_story_state,
    get_or_create_story_progress,
    list_branch_options,
    start_story_branch,
)

router = APIRouter()


@router.get("/branches")
def read_story_branches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = get_or_create_persona(db, current_user)
    return {"items": list_branch_options(current_user, persona)}


@router.get("/progress", response_model=StorySceneRead)
def read_story_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    progress = get_or_create_story_progress(db, current_user)
    return StorySceneRead.model_validate(progress)


@router.get("/state", response_model=StoryStateRead)
def read_story_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = get_or_create_persona(db, current_user)
    return build_story_state(db, current_user, persona)


@router.post("/start", response_model=StoryStateRead, status_code=status.HTTP_201_CREATED)
def create_story_start(
    payload: StoryStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = get_or_create_persona(db, current_user)
    try:
        return start_story_branch(db, current_user, persona, payload.branch_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/choice", response_model=StoryStateRead)
def create_story_choice(
    payload: StoryChoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = get_or_create_persona(db, current_user)
    try:
        return advance_story_choice(db, current_user, persona, payload.choice_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
