from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models.message import MessageEvent
from app.models.npc_session import NpcConversationSession
from app.models.user import User
from app.schemas.internal import InternalUserItem, InternalUsersResponse

router = APIRouter()


def _persona_city(user: User) -> str | None:
    raw_settings = user.persona_profile.raw_settings if user.persona_profile else {}
    if not isinstance(raw_settings, dict):
        return None

    identity = raw_settings.get("identity") or {}
    location = identity.get("location") or {}
    if isinstance(location, dict):
        city = str(location.get("city") or "").strip()
        if city:
            return city

    raw_answers = raw_settings.get("rawAnswers") or {}
    city = str(raw_answers.get("currentLocation") or "").strip()
    return city or None


def _has_bound_persona(user: User) -> bool:
    persona = user.persona_profile
    if persona is None or not isinstance(persona.raw_settings, dict):
        return False

    raw_settings = persona.raw_settings
    identity = raw_settings.get("identity") or {}
    location = identity.get("location") or {}
    return bool(raw_settings.get("profileVersion") and location.get("city"))


def _latest_message_time(messages: Iterable[MessageEvent]) -> object | None:
    timestamps = [message.created_at for message in messages if message.created_at]
    return max(timestamps) if timestamps else None


def _latest_npc_message_time(sessions: Iterable[NpcConversationSession]) -> object | None:
    timestamps = [session.last_message_at for session in sessions if session.last_npc_message]
    return max(timestamps) if timestamps else None


@router.get("/users", response_model=InternalUsersResponse)
def read_internal_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InternalUsersResponse:
    users = list(
        db.scalars(
            select(User)
            .options(
                selectinload(User.persona_profile),
                selectinload(User.message_events),
                selectinload(User.npc_sessions),
            )
            .order_by(User.created_at.desc())
        ).all()
    )

    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0

    items: list[InternalUserItem] = []
    bound_persona_users = 0

    for user in users:
        has_bound = _has_bound_persona(user)
        if has_bound:
            bound_persona_users += 1

        items.append(
            InternalUserItem(
                id=user.id,
                email=user.email,
                username=user.username,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
                persona_display_name=user.persona_profile.display_name if user.persona_profile else None,
                persona_city=_persona_city(user),
                has_bound_persona=has_bound,
                message_count=len(user.message_events),
                unread_message_count=sum(1 for message in user.message_events if message.read_at is None),
                npc_session_count=len(user.npc_sessions),
                latest_message_at=_latest_message_time(user.message_events),
                latest_npc_message_at=_latest_npc_message_time(user.npc_sessions),
            )
        )

    return InternalUsersResponse(
        total_users=len(users),
        active_users=int(active_users),
        bound_persona_users=bound_persona_users,
        items=items,
    )
