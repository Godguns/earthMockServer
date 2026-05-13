from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.message import (
    MessageChannel,
    MessageDeliveryStatus,
    MessageEvent,
    MessageSourceType,
    MessageTriggerType,
)
from app.models.npc_session import NpcConversationSession
from app.models.persona import PersonaProfile
from app.models.user import User
from app.schemas.message import EventTriggerRequest
from app.services.ai_service import NarrativeAIService
from app.services.dify_chat_service import DifyChatError, DifyChatService
from app.services.npc_profiles import (
    build_mother_dify_inputs,
    build_mother_proactive_query,
    build_mother_reply_query,
    get_npc_profile,
)
from app.services.persona_service import get_or_create_persona

MESSAGE_HISTORY_RETENTION_DAYS = 30
MIN_PROACTIVE_MESSAGE_GAP = timedelta(minutes=2)
MOTHER_NPC_KEY = "mother"


def _message_history_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(days=MESSAGE_HISTORY_RETENTION_DAYS)


def prune_expired_messages(db: Session, user_id: UUID | None = None) -> int:
    statement = delete(MessageEvent).where(MessageEvent.created_at < _message_history_cutoff())
    if user_id is not None:
        statement = statement.where(MessageEvent.user_id == user_id)

    result = db.execute(statement)
    deleted_count = result.rowcount or 0
    if deleted_count:
        db.commit()
    return deleted_count


def list_user_messages(
    db: Session,
    user: User,
    channel: MessageChannel | None = None,
    unread_only: bool = False,
    limit: int = 50,
) -> list[MessageEvent]:
    prune_expired_messages(db, user.id)

    query: Select[tuple[MessageEvent]] = select(MessageEvent).where(
        MessageEvent.user_id == user.id,
        MessageEvent.delivery_status != MessageDeliveryStatus.pending,
        MessageEvent.created_at >= _message_history_cutoff(),
    )
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
    prune_expired_messages(db, user.id)
    cutoff = _message_history_cutoff()

    query: Select[tuple[MessageEvent]] = select(MessageEvent).where(
        MessageEvent.user_id == user.id,
        MessageEvent.delivery_status != MessageDeliveryStatus.pending,
        MessageEvent.created_at >= cutoff,
    )
    if since:
        query = query.where(MessageEvent.created_at > max(since, cutoff))
    if channel:
        query = query.where(MessageEvent.channel == channel)

    if since:
        query = query.order_by(MessageEvent.created_at.asc()).limit(limit)
        return list(db.scalars(query).all())

    recent_items = list(
        db.scalars(query.order_by(MessageEvent.created_at.desc()).limit(limit)).all()
    )
    recent_items.reverse()
    return recent_items


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


def _app_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone))
    except Exception:
        return datetime.now(UTC)


def _weekday_label(now_local: datetime) -> str:
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return labels[now_local.weekday()]


def _npc_key_from_conversation_key(conversation_key: str | None) -> str | None:
    if not conversation_key or not conversation_key.startswith("npc:"):
        return None
    _, _, npc_key = conversation_key.partition(":")
    return npc_key.strip() or None


def _get_or_create_npc_session(
    db: Session,
    *,
    user: User,
    npc_key: str,
) -> NpcConversationSession:
    profile = get_npc_profile(npc_key)
    session = db.scalar(
        select(NpcConversationSession).where(
            NpcConversationSession.user_id == user.id,
            NpcConversationSession.npc_key == npc_key,
        )
    )
    if session is not None:
        if not session.conversation_key:
            session.conversation_key = profile.conversation_key
        if not session.dify_user:
            session.dify_user = f"{npc_key}:{user.id}"
        return session

    session = NpcConversationSession(
        user_id=user.id,
        npc_key=npc_key,
        conversation_key=profile.conversation_key,
        dify_user=f"{npc_key}:{user.id}",
        meta={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _build_last_chat_summary(
    db: Session,
    *,
    user_id: UUID,
    conversation_key: str,
    limit: int = 6,
) -> str:
    items = list(
        db.scalars(
            select(MessageEvent)
            .where(
                MessageEvent.user_id == user_id,
                MessageEvent.channel == MessageChannel.chat,
                MessageEvent.conversation_key == conversation_key,
                MessageEvent.created_at >= _message_history_cutoff(),
            )
            .order_by(MessageEvent.created_at.desc())
            .limit(limit)
        ).all()
    )
    if not items:
        return "暂无聊天记录"

    items.reverse()
    fragments: list[str] = []
    for item in items:
        if item.payload.get("kind") == "player_message":
            speaker = "我"
        else:
            speaker = item.sender_name or "对方"
        compact_text = " ".join(str(item.content or "").split())
        if not compact_text:
            continue
        if len(compact_text) > 32:
            compact_text = f"{compact_text[:32]}..."
        fragments.append(f"{speaker}：{compact_text}")

    return "；".join(fragments[-4:]) or "暂无聊天记录"


def _resolve_mother_trigger(session: NpcConversationSession) -> str:
    now_local = _app_now()
    hour = now_local.hour
    if session.last_message_at:
        gap = now_local.astimezone(UTC) - session.last_message_at
        if gap >= timedelta(days=5):
            return "holiday_check_in"
    if hour < 10:
        return "morning_greeting"
    if hour >= 22 or hour <= 4:
        return "late_night_check"

    bucket = now_local.weekday() % 3
    if bucket == 0:
        return "job_follow_up"
    if bucket == 1:
        return "money_concern"
    return "weather_care"


def _build_mother_runtime_context(
    db: Session,
    *,
    user: User,
    session: NpcConversationSession,
    event_hint: str | None = None,
) -> dict[str, str]:
    now_local = _app_now()
    now_utc = now_local.astimezone(UTC)
    days_since_last_chat = 1
    if session.last_message_at:
        delta = now_utc.date() - session.last_message_at.date()
        days_since_last_chat = max(delta.days, 0)

    return {
        "game_time": now_local.strftime("%Y-%m-%d %H:%M"),
        "game_day_of_week": _weekday_label(now_local),
        "days_since_last_chat": str(days_since_last_chat),
        "last_chat_summary": _build_last_chat_summary(
            db,
            user_id=user.id,
            conversation_key=session.conversation_key,
        ),
        "event_hint": event_hint or "",
    }


def _normalize_dify_npc_response(
    raw_response: dict[str, Any],
    *,
    default_title: str,
    default_should_notify: bool,
) -> dict[str, Any]:
    content = str(raw_response.get("content") or "").strip()
    if not content:
        raise ValueError("NPC response content was empty.")

    return {
        "title": str(raw_response.get("title") or default_title).strip() or default_title,
        "content": content,
        "should_notify": bool(raw_response.get("should_notify", default_should_notify)),
        "emotion": str(raw_response.get("emotion") or "concerned").strip() or "concerned",
        "provider": str(raw_response.get("provider") or "dify"),
        "dify_message_id": raw_response.get("dify_message_id"),
        "dify_task_id": raw_response.get("dify_task_id"),
        "dify_conversation_id": raw_response.get("dify_conversation_id"),
    }


def _normalize_plaintext_dify_response(
    answer: str,
    *,
    default_title: str,
    default_should_notify: bool,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = str(answer or "").strip()
    if not content:
        raise ValueError("NPC plaintext response content was empty.")

    extra = metadata or {}
    return {
        "title": default_title,
        "content": content,
        "should_notify": default_should_notify,
        "emotion": "concerned",
        "provider": "dify",
        "dify_message_id": extra.get("dify_message_id"),
        "dify_task_id": extra.get("dify_task_id"),
        "dify_conversation_id": extra.get("dify_conversation_id"),
    }


def _fallback_mother_response(
    *,
    trigger_type: str,
    player_message: str | None = None,
) -> dict[str, Any]:
    if trigger_type == "morning_greeting":
        content = "起了没，早饭记得吃。"
    elif trigger_type == "late_night_check":
        content = "怎么还没睡，别又熬夜啊。"
    elif trigger_type == "job_follow_up":
        content = "工作这阵子怎么样，别太硬扛。"
    elif trigger_type == "money_concern":
        content = "钱够不够花，不够就跟我说。"
    elif trigger_type == "weather_care":
        content = "今天天气变了，出门多穿点。"
    elif trigger_type == "holiday_check_in":
        content = "这几天忙不忙，有空回个消息。"
    elif trigger_type == "player_reply":
        content = "知道了，你先忙，记得吃饭。"
        if player_message and any(keyword in player_message for keyword in ("累", "烦", "忙")):
            content = "那你先忙完，别老扛着，饭也要吃。"
    else:
        content = "家里一切都好，你忙完回我一下。"

    return {
        "title": "妈妈",
        "content": content,
        "should_notify": trigger_type != "player_reply",
        "emotion": "concerned",
        "provider": "fallback",
        "dify_message_id": None,
        "dify_task_id": None,
        "dify_conversation_id": None,
    }


def _request_mother_response(
    *,
    profile,
    session: NpcConversationSession,
    query: str,
    inputs: dict[str, Any],
    trigger_type: str,
    player_message: str | None = None,
    default_should_notify: bool = True,
) -> dict[str, Any]:
    if not profile.dify_api_key:
        return _fallback_mother_response(
            trigger_type=trigger_type,
            player_message=player_message,
        )

    response = DifyChatService.send_blocking_message(
        api_key=profile.dify_api_key,
        query=query,
        inputs=inputs,
        user_identifier=session.dify_user,
        conversation_id=session.dify_conversation_id,
        workflow_id=profile.workflow_id,
    )
    try:
        parsed = DifyChatService.parse_json_answer(response["answer"])
    except DifyChatError:
        return _normalize_plaintext_dify_response(
            response.get("answer", ""),
            default_title=profile.display_name,
            default_should_notify=default_should_notify,
            metadata={
                "dify_message_id": response.get("message_id"),
                "dify_task_id": response.get("task_id"),
                "dify_conversation_id": response.get("conversation_id"),
            },
        )
    return _normalize_dify_npc_response(
        {
            **parsed,
            "provider": "dify",
            "dify_message_id": response.get("message_id"),
            "dify_task_id": response.get("task_id"),
            "dify_conversation_id": response.get("conversation_id"),
        },
        default_title=profile.display_name,
        default_should_notify=default_should_notify,
    )


def _update_npc_session_from_player(
    db: Session,
    *,
    session: NpcConversationSession,
    content: str,
) -> None:
    now = datetime.now(UTC)
    meta = dict(session.meta or {})
    meta["last_player_message_at"] = now.isoformat()
    meta["last_player_message_preview"] = content[:80]
    session.last_message_at = now
    session.last_player_message = content
    session.meta = meta
    db.add(session)
    db.commit()
    db.refresh(session)


def _update_npc_session_from_npc(
    db: Session,
    *,
    session: NpcConversationSession,
    trigger_type: str,
    response: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    meta = dict(session.meta or {})
    meta["last_trigger_type"] = trigger_type
    meta["last_npc_emotion"] = response.get("emotion")
    meta["last_provider"] = response.get("provider")
    meta["last_should_notify"] = response.get("should_notify")
    if response.get("dify_task_id"):
        meta["last_dify_task_id"] = response["dify_task_id"]
    if response.get("dify_message_id"):
        meta["last_dify_message_id"] = response["dify_message_id"]

    session.last_message_at = now
    session.last_npc_message = response["content"]
    session.meta = meta
    if response.get("dify_conversation_id"):
        session.dify_conversation_id = str(response["dify_conversation_id"])
    db.add(session)
    db.commit()
    db.refresh(session)


def _should_skip_proactive_push(session: NpcConversationSession) -> bool:
    if session.last_message_at is None:
        return False
    return datetime.now(UTC) - session.last_message_at < MIN_PROACTIVE_MESSAGE_GAP


def _build_mother_player_message_events(
    db: Session,
    *,
    user: User,
    profile,
    content: str,
    client_message_id: str | None,
) -> list[MessageEvent]:
    return _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=[MessageChannel.chat],
        source_type=MessageSourceType.system,
        trigger_type=MessageTriggerType.manual,
        title=profile.display_name,
        content=content,
        sender_name=user.username,
        conversation_key=profile.conversation_key,
        payload={
            "kind": "player_message",
            "client_message_id": client_message_id,
            "partner_name": profile.display_name,
            "npc_key": profile.key,
        },
        scheduled_for=None,
    )


def _build_mother_npc_message_events(
    db: Session,
    *,
    user: User,
    profile,
    trigger_type: MessageTriggerType,
    response: dict[str, Any],
    client_message_id: str | None = None,
    include_notification: bool,
    payload_kind: str,
    resolved_trigger: str,
) -> list[MessageEvent]:
    channel_targets = [MessageChannel.chat]
    if include_notification and response.get("should_notify", True):
        channel_targets.insert(0, MessageChannel.notification)

    return _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=channel_targets,
        source_type=MessageSourceType.npc,
        trigger_type=trigger_type,
        title=response["title"],
        content=response["content"],
        sender_name=profile.display_name,
        conversation_key=profile.conversation_key,
        payload={
            "kind": payload_kind,
            "npc_key": profile.key,
            "emotion": response.get("emotion"),
            "provider": response.get("provider"),
            "should_notify": response.get("should_notify", True),
            "reply_to_client_message_id": client_message_id,
            "resolved_trigger_type": resolved_trigger,
            "dify_message_id": response.get("dify_message_id"),
            "dify_task_id": response.get("dify_task_id"),
        },
        scheduled_for=None,
    )


def generate_random_message_for_user(db: Session, user: User) -> list[MessageEvent]:
    prune_expired_messages(db, user.id)
    persona = get_or_create_persona(db, user)
    profile = get_npc_profile(MOTHER_NPC_KEY)
    session = _get_or_create_npc_session(db, user=user, npc_key=profile.key)

    if _should_skip_proactive_push(session):
        if persona.npc_push_enabled:
            _schedule_next_random_push(persona)
            db.add(persona)
            db.commit()
        return []

    resolved_trigger = _resolve_mother_trigger(session)
    runtime_context = _build_mother_runtime_context(db, user=user, session=session)
    inputs = build_mother_dify_inputs(
        persona,
        user,
        trigger_type=resolved_trigger,
        runtime_context=runtime_context,
    )
    query = build_mother_proactive_query(resolved_trigger, runtime_context)
    response = _request_mother_response(
        profile=profile,
        session=session,
        query=query,
        inputs=inputs,
        trigger_type=resolved_trigger,
        default_should_notify=True,
    )

    _update_npc_session_from_npc(
        db,
        session=session,
        trigger_type=resolved_trigger,
        response=response,
    )

    created = _build_mother_npc_message_events(
        db,
        user=user,
        profile=profile,
        trigger_type=MessageTriggerType.random,
        response=response,
        include_notification=True,
        payload_kind="npc_random_push",
        resolved_trigger=resolved_trigger,
    )

    if persona.npc_push_enabled:
        _schedule_next_random_push(persona)
        db.add(persona)
        db.commit()
    return created


def create_event_messages(db: Session, user: User, payload: EventTriggerRequest) -> list[MessageEvent]:
    prune_expired_messages(db, user.id)
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


def _create_non_npc_reply_ack(
    db: Session,
    user: User,
    *,
    content: str,
    conversation_key: str | None = None,
    sender_name: str | None = None,
    title: str | None = None,
    client_message_id: str | None = None,
) -> list[MessageEvent]:
    persona = get_or_create_persona(db, user)
    summary = _build_persona_summary(persona, user)
    reply_sender = sender_name or "Earth Online"
    reply_title = title or f"{reply_sender} acknowledged your message"
    effective_conversation_key = conversation_key or f"system:{reply_sender}"

    player_messages = _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=[MessageChannel.chat],
        source_type=MessageSourceType.system,
        trigger_type=MessageTriggerType.manual,
        title=reply_sender,
        content=content,
        sender_name=user.username,
        conversation_key=effective_conversation_key,
        payload={
            "kind": "player_message",
            "client_message_id": client_message_id,
            "partner_name": reply_sender,
        },
        scheduled_for=None,
    )

    reply_content = (
        f"AI能力还在完善中（收到你的消息：{content}；当前主要人格信息：{summary}）"
    )
    ack_messages = _create_fanout_messages(
        db,
        user_id=user.id,
        channel_targets=[MessageChannel.notification, MessageChannel.chat],
        source_type=MessageSourceType.system,
        trigger_type=MessageTriggerType.manual,
        title=reply_title,
        content=reply_content,
        sender_name=reply_sender,
        conversation_key=effective_conversation_key,
        payload={
            "kind": "player_reply_ack",
            "player_message": content,
            "persona_summary": summary,
            "reply_to_client_message_id": client_message_id,
        },
        scheduled_for=None,
    )
    return [*player_messages, *ack_messages]


def create_player_reply_ack(
    db: Session,
    user: User,
    *,
    content: str,
    conversation_key: str | None = None,
    sender_name: str | None = None,
    title: str | None = None,
    client_message_id: str | None = None,
) -> list[MessageEvent]:
    prune_expired_messages(db, user.id)
    npc_key = _npc_key_from_conversation_key(conversation_key)
    if npc_key != MOTHER_NPC_KEY:
        return _create_non_npc_reply_ack(
            db,
            user,
            content=content,
            conversation_key=conversation_key,
            sender_name=sender_name,
            title=title,
            client_message_id=client_message_id,
        )

    persona = get_or_create_persona(db, user)
    profile = get_npc_profile(MOTHER_NPC_KEY)
    session = _get_or_create_npc_session(db, user=user, npc_key=profile.key)

    player_messages = _build_mother_player_message_events(
        db,
        user=user,
        profile=profile,
        content=content,
        client_message_id=client_message_id,
    )
    _update_npc_session_from_player(db, session=session, content=content)

    runtime_context = _build_mother_runtime_context(db, user=user, session=session)
    inputs = build_mother_dify_inputs(
        persona,
        user,
        trigger_type="player_reply",
        runtime_context=runtime_context,
    )
    query = build_mother_reply_query(content)
    response = _request_mother_response(
        profile=profile,
        session=session,
        query=query,
        inputs=inputs,
        trigger_type="player_reply",
        player_message=content,
        default_should_notify=False,
    )
    _update_npc_session_from_npc(
        db,
        session=session,
        trigger_type="player_reply",
        response=response,
    )

    npc_messages = _build_mother_npc_message_events(
        db,
        user=user,
        profile=profile,
        trigger_type=MessageTriggerType.manual,
        response=response,
        client_message_id=client_message_id,
        include_notification=False,
        payload_kind="npc_message",
        resolved_trigger="player_reply",
    )
    return [*player_messages, *npc_messages]


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
    prune_expired_messages(db)
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
        created_messages = generate_random_message_for_user(db, user)
        if created_messages:
            created_count += 1
    return created_count


def _build_persona_summary(persona: PersonaProfile, user: User) -> str:
    raw_settings = persona.raw_settings if isinstance(persona.raw_settings, dict) else {}
    identity = raw_settings.get("identity") or {}
    anchors = raw_settings.get("anchors") or {}
    tags = raw_settings.get("tags") or []
    save_model = raw_settings.get("saveModel") or {}
    soul = anchors.get("soul") or {}
    finance = anchors.get("finance") or {}

    parts = [
        identity.get("name") or persona.display_name or user.username,
        identity.get("careerStatus"),
        soul.get("desire"),
        finance.get("cashFlow"),
    ]

    for key in ("social", "attribute", "vitality", "event"):
        label = (save_model.get(key) or {}).get("label")
        if label:
            parts.append(label)

    parts.extend(tags[:3] if isinstance(tags, list) else [])
    normalized_parts = [str(item).strip() for item in parts if str(item).strip()]
    return " | ".join(normalized_parts[:8]) or user.username
