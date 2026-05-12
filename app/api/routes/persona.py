from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.persona import FrontendPersonaProfile, PersonaRead, PersonaUpsertRequest
from app.services.persona_service import (
    bind_frontend_persona,
    get_or_create_persona,
    upsert_persona,
)

router = APIRouter()


@router.get("/me", response_model=PersonaRead)
def read_persona(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonaRead:
    persona = get_or_create_persona(db, current_user)
    return PersonaRead.model_validate(persona)


@router.put("/me", response_model=PersonaRead)
def save_persona(
    payload: PersonaUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonaRead:
    persona = upsert_persona(db, current_user, payload)
    return PersonaRead.model_validate(persona)


@router.put("/bind", response_model=PersonaRead)
def bind_persona_profile(
    payload: FrontendPersonaProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PersonaRead:
    persona = bind_frontend_persona(db, current_user, payload)
    return PersonaRead.model_validate(persona)
