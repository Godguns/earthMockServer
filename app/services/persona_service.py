from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.persona import PersonaProfile
from app.models.user import User
from app.schemas.persona import FrontendPersonaProfile, PersonaUpsertRequest


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


def bind_frontend_persona(
    db: Session,
    user: User,
    payload: FrontendPersonaProfile,
) -> PersonaProfile:
    persona = get_or_create_persona(db, user)
    profile = payload.model_dump(mode="json")
    identity = profile.get("identity") or {}
    anchors = profile.get("anchors") or {}
    save_model = profile.get("saveModel") or {}
    signals = profile.get("signals") or {}
    raw_answers = profile.get("rawAnswers") or {}

    persona.display_name = identity.get("name") or raw_answers.get("playerName") or user.username
    persona.archetype = _build_archetype(save_model, profile.get("tags") or [])
    persona.world_context = _build_world_context(identity, anchors)
    persona.backstory = _build_backstory(identity, anchors)
    persona.system_prompt = _build_system_prompt()
    persona.communication_style = _build_communication_style(signals)
    persona.emotional_traits = _as_string_list(signals.get("pressureTriggers"))
    persona.favorite_topics = _as_string_list(profile.get("tags"))
    persona.boundaries = _as_string_list(signals.get("comfortZones"))
    persona.relationship_goals = _as_string_list(signals.get("relationshipLens"))
    persona.raw_settings = profile

    if persona.npc_push_enabled and persona.next_npc_push_at is None:
        persona.next_npc_push_at = datetime.now(UTC) + timedelta(
            minutes=persona.npc_push_frequency_minutes
        )

    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_archetype(save_model: dict, tags: list[str]) -> str | None:
    if save_model:
        parts = []
        for key in ("social", "attribute", "vitality", "event"):
            item = save_model.get(key) or {}
            if item.get("label"):
                parts.append(str(item["label"]))
        if parts:
            return " / ".join(parts)
    if tags:
        return " / ".join(tags[:3])
    return None


def _build_world_context(identity: dict, anchors: dict) -> str | None:
    origin = anchors.get("origin") or {}
    career = identity.get("careerStatus")
    birthplace = origin.get("birthplace")
    family = origin.get("familyType")
    parts = [item for item in [birthplace, family, career] if item]
    return " | ".join(str(item) for item in parts) or None


def _build_backstory(identity: dict, anchors: dict) -> str | None:
    origin = anchors.get("origin") or {}
    soul = anchors.get("soul") or {}
    body = anchors.get("body") or {}
    lines = [
        f"name: {identity.get('name')}" if identity.get("name") else None,
        f"birth_date: {identity.get('birthDate')}" if identity.get("birthDate") else None,
        f"family_expectation: {origin.get('familyExpectation')}"
        if origin.get("familyExpectation")
        else None,
        f"fear: {soul.get('fear')}" if soul.get("fear") else None,
        f"desire: {soul.get('desire')}" if soul.get("desire") else None,
        f"relax_mode: {body.get('relaxMode')}" if body.get("relaxMode") else None,
    ]
    return "\n".join(line for line in lines if line) or None


def _build_system_prompt() -> str:
    return (
        "Generate a personalized Earth Online experience for this player. "
        "Prioritize persona.raw_settings.identity, anchors, saveModel and signals. "
        "Keep the writing realistic, restrained and introspective."
    )


def _build_communication_style(signals: dict) -> str | None:
    pressure = _as_string_list(signals.get("pressureTriggers"))
    comfort = _as_string_list(signals.get("comfortZones"))
    pieces = []
    if pressure:
        pieces.append(f"pressure_triggers: {' / '.join(pressure[:4])}")
    if comfort:
        pieces.append(f"comfort_zones: {' / '.join(comfort[:4])}")
    return " | ".join(pieces) or None
