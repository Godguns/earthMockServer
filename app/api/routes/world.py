from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.world import WorldActionRequest, WorldStateRead
from app.services.world_service import apply_world_action, build_world_state_read

router = APIRouter()


@router.get("/state", response_model=WorldStateRead)
def read_world_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorldStateRead:
    return build_world_state_read(db, current_user)


@router.post("/action", response_model=WorldStateRead)
def create_world_action(
    payload: WorldActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorldStateRead:
    return apply_world_action(db, current_user, payload.action_key)
