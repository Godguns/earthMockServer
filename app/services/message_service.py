from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.message import (
    MessageChannel,
    MessageDeliveryStatus,
    MessageEvent,
    MessageSourceType,
    MessageTriggerType,
)
from app.models.persona import PersonaProfile
from app.models.user import User
from app.schemas.message import EventTriggerRequest
from app.services.ai_service import NarrativeAIService
from app.services.persona_service import get_or_create_persona


def list_user_messages(
    db: Session,
    user: User,
    channel: MessageChannel | None = None,
    unread_only: bool = False,
    limit: int = 50,
) -> list[MessageEvent]:
    query: Select[tuple[MessageEvent]] = select(MessageEvent).where(MessageEvent.user_id == user.id)
    query = query.where(MessageEvent.delivery_status != MessageDeliveryStatus.pending)
    if channel:
        query = query.where(MessageEvent.channel == channel)
    if unread_only:
        query = query.where(MessageEvent.read_at.is_(None))
    query = query.order_by(MessageEvent.created_at.desc()).limit(limit)
    return list(db.scalars(query).all())


def list_new_user_messages(
    db: Session,
    user: User,
    since: datetime | None = None,
    channel: MessageChannel | None = None,
    limit: int = 50,
) -> list[MessageEvent]:
    query: Select[tuple[MessageEvent]] = select(MessageEvent).where(
        MessageEvent.user_id == user.id,
        MessageEvent.delivery_status != MessageDeliveryStatus.pending,
    )
    if since:
        query = query.where(MessageEvent.created_at > since)
    if channel:
        query = query.where(MessageEvent.channel == channel)
    query = query.order_by(MessageEvent.created_at.asc()).limit(limit)
    return list(db.scalars(query).all())


def _build_message(
    *,
    user_id: UUID,
    channel: MessageChannel,
    source_type: MessageSourceType,
    trigger_type: MessageTriggerType,
    title: str | None,
    content: str,
    sender_name: str,
    conversation_key: str | None,
    payload: dict,
    scheduled_for: datetime | None,
) -> MessageEvent:
    now = datetime.now(UTC)
    is_immediate = scheduled_for is None or scheduled_for <= now
    return MessageEvent(
        user_id=user_id,
        channel=channel,
        source_type=source_type,
        trigger_type=trigger_type,
        title=title,
        content=content,
        sender_name=sender_name,
        conversation_key=conversation_key,
        payload=payload,
        scheduled_for=scheduled_for,
        delivery_status=(
            MessageDeliveryStatus.delivered if is_immediate else MessageDeliveryStatus.pending
        ),
        delivered_at=now if is_immediate else None,
    )


def _create_fanout_messages(
    db: Session,
    *,
    user_id: UUID,
    channel_targets: list[MessageChannel],
    source_type: MessageSourceType,
    trigger_type: MessageTriggerType,
    title: str | None,
    content: str,
    sender_name: str,
    conversation_key: str | None,
    payload: dict,
    scheduled_for: datetime | None,
) -> list[MessageEvent]:
    created: list[MessageEvent] = []
    for channel in channel_targets:
        event = _build_message(
            user_id=user_id,
            channel=channel,
            source_type=source_type,
            trigger_type=trigger_type,
            title=title,
            content=content,
            sender_name=sender_name,
            conversation_key=conversation_key,
            payload=payload,
            scheduled_for=scheduled_for,
        )
        db.add(event)
        created.append(event)
    db.commit()
    for item in created:
        db.refresh(item)
    return created


def _schedule_next_random_push(persona: PersonaProfile) -> None:
    jitter = random.randint(0, settings.npc_random_jitter_minutes)
    persona.next_npc_push_at = datetime.now(UTC) + timedelta(
        minutes=persona.npc_push_frequency_minutes + jitter
    )


def generate_random_message_for_user(db: Session, user: User) -> list[MessageEvent]:
    persona = get_or_create_persona(db, user)
    message = NarrativeAIService.build_random_npc_message(persona)
    created = _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=[MessageChannel.notification, MessageChannel.chat],
        source_type=MessageSourceType.npc,
        trigger_type=MessageTriggerType.random,
        title=message["title"],
        content=message["content"],
        sender_name=message["speaker"],
        conversation_key=f"npc:{message['speaker']}",
        payload={"kind": "npc_random_push"},
        scheduled_for=None,
    )
    if persona.npc_push_enabled:
        _schedule_next_random_push(persona)
        db.add(persona)
        db.commit()
    return created


def create_event_messages(db: Session, user: User, payload: EventTriggerRequest) -> list[MessageEvent]:
    persona = get_or_create_persona(db, user)
    generated = NarrativeAIService.build_event_message(persona, payload.trigger_name, payload.content)
    return _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=payload.channel_targets,
        source_type=payload.source_type,
        trigger_type=(
            MessageTriggerType.scheduled if payload.scheduled_for else MessageTriggerType.event
        ),
        title=payload.title or generated["title"],
        content=generated["content"],
        sender_name=payload.sender_name or generated["speaker"],
        conversation_key=payload.conversation_key,
        payload={**payload.payload, "trigger_name": payload.trigger_name},
        scheduled_for=payload.scheduled_for,
    )


def mark_message_as_read(db: Session, user: User, message_id: UUID) -> MessageEvent | None:
    message = db.scalar(
        select(MessageEvent).where(MessageEvent.id == message_id, MessageEvent.user_id == user.id)
    )
    if message is None:
        return None
    if message.read_at is None:
        message.read_at = datetime.now(UTC)
        message.delivery_status = MessageDeliveryStatus.read
        db.add(message)
        db.commit()
        db.refresh(message)
    return message


def deliver_due_messages(db: Session) -> int:
    now = datetime.now(UTC)
    items = list(
        db.scalars(
            select(MessageEvent).where(
                MessageEvent.delivery_status == MessageDeliveryStatus.pending,
                MessageEvent.scheduled_for.is_not(None),
                MessageEvent.scheduled_for <= now,
            )
        ).all()
    )
    for item in items:
        item.delivery_status = MessageDeliveryStatus.delivered
        item.delivered_at = now
        db.add(item)
    if items:
        db.commit()
    return len(items)


def run_random_push_cycle(db: Session) -> int:
    now = datetime.now(UTC)
    due_personas = list(
        db.scalars(
            select(PersonaProfile).where(
                PersonaProfile.npc_push_enabled.is_(True),
                PersonaProfile.next_npc_push_at.is_not(None),
                PersonaProfile.next_npc_push_at <= now,
            )
        ).all()
    )
    created_count = 0
    for persona in due_personas:
        user = db.get(User, persona.user_id)
        if user is None:
            continue
        generate_random_message_for_user(db, user)
        created_count += 1
    return created_count
