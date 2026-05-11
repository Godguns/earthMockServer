from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.persona import PersonaProfile
from app.models.user import User
from app.schemas.persona import PersonaUpsertRequest


def get_or_create_persona(db: Session, user: User) -> PersonaProfile:
    persona = db.scalar(select(PersonaProfile).where(PersonaProfile.user_id == user.id))
    if persona:
        return persona

    persona = PersonaProfile(
        user_id=user.id,
        npc_push_frequency_minutes=settings.npc_default_interval_minutes,
        next_npc_push_at=datetime.now(UTC) + timedelta(minutes=settings.npc_default_interval_minutes),
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def upsert_persona(db: Session, user: User, payload: PersonaUpsertRequest) -> PersonaProfile:
    persona = get_or_create_persona(db, user)

    persona.display_name = payload.display_name
    persona.archetype = payload.archetype
    persona.world_context = payload.world_context
    persona.backstory = payload.backstory
    persona.system_prompt = payload.system_prompt
    persona.communication_style = payload.communication_style
    persona.emotional_traits = payload.emotional_traits
    persona.favorite_topics = payload.favorite_topics
    persona.boundaries = payload.boundaries
    persona.relationship_goals = payload.relationship_goals
    persona.raw_settings = payload.raw_settings
    persona.npc_push_enabled = payload.npc_push_enabled
    persona.npc_push_frequency_minutes = payload.npc_push_frequency_minutes

    if persona.npc_push_enabled and persona.next_npc_push_at is None:
        persona.next_npc_push_at = datetime.now(UTC) + timedelta(
            minutes=payload.npc_push_frequency_minutes
        )
    if not persona.npc_push_enabled:
        persona.next_npc_push_at = None

    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona

