from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.message import MessageChannel, MessageSourceType
from app.models.persona import PersonaProfile
from app.models.user import User
from app.models.world import PlayerWorldEvent, PlayerWorldState
from app.schemas.message import EventTriggerRequest
from app.schemas.world import WorldStateRead
from app.services.message_service import create_event_messages


DEFAULT_ACTIONS = [
    "处理账单",
    "早点休息",
    "给母亲回消息",
    "出去走走",
    "认真沟通",
    "接住机会",
]


def clamp01(value: float) -> float:
    return min(max(value, 0), 1)


def get_or_create_world_state(db: Session, user: User) -> PlayerWorldState:
    state = db.scalar(select(PlayerWorldState).where(PlayerWorldState.user_id == user.id))
    if state:
        return state

    state = PlayerWorldState(user_id=user.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    seed_world_events(db, user, state)
    return state


def list_world_events(db: Session, user: User, limit: int = 6) -> list[PlayerWorldEvent]:
    return list(
        db.scalars(
            select(PlayerWorldEvent)
            .where(
                PlayerWorldEvent.user_id == user.id,
                PlayerWorldEvent.status == "active",
            )
            .order_by(PlayerWorldEvent.created_at.desc())
            .limit(limit)
        ).all()
    )


def build_world_state_read(db: Session, user: User) -> WorldStateRead:
    state = get_or_create_world_state(db, user)
    events = list_world_events(db, user)
    return WorldStateRead(
        money={
            "balance": state.money_balance,
            "income_monthly": state.money_income_monthly,
            "expense_monthly": state.money_expense_monthly,
            "pressure": state.money_pressure,
        },
        health={
            "energy": state.health_energy,
            "sleep": state.health_sleep,
            "body": state.health_body,
        },
        mood={
            "stability": state.mood_stability,
            "anxiety": state.mood_anxiety,
            "loneliness": state.mood_loneliness,
        },
        relations={
            "mother": state.relation_mother,
            "friends": state.relation_friends,
            "work": state.relation_work,
            "institution": state.relation_institution,
        },
        time={
            "day_label": state.day_label,
            "deadline_label": state.deadline_label,
            "phase_key": state.phase_key,
        },
        events=events,
        actions=list(DEFAULT_ACTIONS),
        journal=_build_world_journal(state, events),
    )


def seed_world_events(db: Session, user: User, state: PlayerWorldState) -> None:
    existing = db.scalar(
        select(PlayerWorldEvent).where(
            PlayerWorldEvent.user_id == user.id,
            PlayerWorldEvent.status == "active",
        )
    )
    if existing:
        return

    templates = [
        {
            "event_key": "rent_due",
            "tone": "danger",
            "title": "房租提醒",
            "subtitle": "这笔支出会直接影响你接下来几天的现金流。",
            "source": "房东",
            "priority": "high",
            "due_in": "3天",
            "consequence": "若继续拖延，焦虑会上升，母亲更可能主动过问。",
        },
        {
            "event_key": "sleep_debt",
            "tone": "warn",
            "title": "睡眠债累积",
            "subtitle": "你已经连续几天休息不足，恢复效率正在下降。",
            "source": "身体",
            "priority": "medium",
            "due_in": "今天",
            "consequence": "继续拖延会降低精力，并触发更多低落情绪。",
        },
        {
            "event_key": "mother_attention",
            "tone": "info",
            "title": "母亲察觉到异常",
            "subtitle": "她注意到你最近回复变慢了，可能会主动来问。",
            "source": "母亲",
            "priority": "medium",
            "due_in": "现在",
            "consequence": "回应方式会影响关系值，也会影响后续主动消息。",
        },
    ]

    for template in templates:
        db.add(PlayerWorldEvent(user_id=user.id, payload={}, **template))

    db.commit()


def apply_world_action(db: Session, user: User, action_key: str) -> WorldStateRead:
    state = get_or_create_world_state(db, user)

    if action_key == "处理账单":
        state.money_balance -= 860
        state.money_pressure = clamp01(state.money_pressure - 0.12)
        state.mood_anxiety = clamp01(state.mood_anxiety - 0.05)
        state.mood_stability = clamp01(state.mood_stability + 0.04)
        _resolve_event_by_key(db, user, "rent_due")
    elif action_key == "早点休息":
        state.health_energy = clamp01(state.health_energy + 0.1)
        state.health_sleep = clamp01(state.health_sleep + 0.14)
        state.mood_anxiety = clamp01(state.mood_anxiety - 0.04)
        state.mood_stability = clamp01(state.mood_stability + 0.05)
        _resolve_event_by_key(db, user, "sleep_debt")
    elif action_key == "给母亲回消息":
        state.relation_mother = clamp01(state.relation_mother + 0.08)
        state.mood_loneliness = clamp01(state.mood_loneliness - 0.05)
        state.mood_stability = clamp01(state.mood_stability + 0.03)
        _resolve_event_by_key(db, user, "mother_attention")
    elif action_key == "出去走走":
        state.health_energy = clamp01(state.health_energy + 0.06)
        state.mood_stability = clamp01(state.mood_stability + 0.05)
        state.mood_loneliness = clamp01(state.mood_loneliness - 0.04)
    elif action_key == "认真沟通":
        state.relation_mother = clamp01(state.relation_mother + 0.1)
        state.relation_friends = clamp01(state.relation_friends + 0.04)
        state.mood_stability = clamp01(state.mood_stability + 0.04)
        state.mood_anxiety = clamp01(state.mood_anxiety - 0.03)
    elif action_key == "接住机会":
        state.money_balance += 260
        state.money_pressure = clamp01(state.money_pressure - 0.04)
        state.health_energy = clamp01(state.health_energy - 0.03)
        state.mood_stability = clamp01(state.mood_stability + 0.03)

    db.add(state)
    db.commit()
    db.refresh(state)
    ensure_state_driven_events(db, user, state)
    return build_world_state_read(db, user)


def ensure_state_driven_events(db: Session, user: User, state: PlayerWorldState) -> None:
    active_keys = {
        item.event_key
        for item in db.scalars(
            select(PlayerWorldEvent).where(
                PlayerWorldEvent.user_id == user.id,
                PlayerWorldEvent.status == "active",
            )
        ).all()
    }

    candidates: list[dict] = []

    if state.money_balance < 1800 and "cash_crunch" not in active_keys:
        candidates.append(
            {
                "event_key": "cash_crunch",
                "tone": "danger",
                "title": "现金流变紧",
                "subtitle": "余额开始逼近高压区，需要尽快做收入或支出决策。",
                "source": "系统",
                "priority": "high",
                "due_in": "48小时",
                "consequence": "若继续下降，将更频繁触发账单与机会事件。",
            }
        )

    if state.health_energy < 0.48 and "energy_low" not in active_keys:
        candidates.append(
            {
                "event_key": "energy_low",
                "tone": "warn",
                "title": "精力处于低位",
                "subtitle": "你的恢复速度明显下降，继续透支会影响更多行动结果。",
                "source": "身体",
                "priority": "medium",
                "due_in": "今晚",
                "consequence": "若不恢复，后续工作类选择收益会下降。",
            }
        )

    if state.relation_mother < 0.58 and "mother_distance" not in active_keys:
        candidates.append(
            {
                "event_key": "mother_distance",
                "tone": "info",
                "title": "关系正在疏远",
                "subtitle": "母亲开始感知到你在回避沟通。",
                "source": "母亲",
                "priority": "medium",
                "due_in": "最近",
                "consequence": "主动消息会更偏向试探与担忧。",
            }
        )

    for candidate in candidates:
        db.add(PlayerWorldEvent(user_id=user.id, payload={}, **candidate))

    if candidates:
        db.commit()


def build_world_event_hint(db: Session, user: User) -> str | None:
    events = list_world_events(db, user, limit=2)
    if not events:
        return None
    return " | ".join(f"{event.title}:{event.priority}" for event in events)


def maybe_emit_world_push(db: Session, user: User, persona: PersonaProfile | None = None) -> None:
    state = get_or_create_world_state(db, user)
    events = list_world_events(db, user, limit=1)
    if not events:
        return

    top_event = events[0]
    if top_event.priority != "high":
        return

    if top_event.payload.get("message_emitted"):
        return

    create_event_messages(
        db,
        user,
        EventTriggerRequest(
            trigger_name=top_event.event_key,
            title=top_event.title,
            content=f"{top_event.subtitle} {top_event.consequence}",
            sender_name=top_event.source,
            source_type=MessageSourceType.event,
            channel_targets=[MessageChannel.notification, MessageChannel.chat],
            payload={
                "kind": "world_event_push",
                "event_key": top_event.event_key,
                "phase_key": state.phase_key,
            },
        ),
    )
    top_event.payload = {**(top_event.payload or {}), "message_emitted": True}
    db.add(top_event)
    db.commit()


def apply_story_world_effects(db: Session, user: User, world_effects: dict | None) -> None:
    if not world_effects:
        return

    state = get_or_create_world_state(db, user)
    money = world_effects.get("money") or {}
    health = world_effects.get("health") or {}
    mood = world_effects.get("mood") or {}
    relations = world_effects.get("relations") or {}

    state.money_balance += int(money.get("balance", 0) or 0)
    state.money_pressure = clamp01(state.money_pressure + float(money.get("pressure", 0) or 0))

    state.health_energy = clamp01(state.health_energy + float(health.get("energy", 0) or 0))
    state.health_sleep = clamp01(state.health_sleep + float(health.get("sleep", 0) or 0))
    state.health_body = clamp01(state.health_body + float(health.get("body", 0) or 0))

    state.mood_stability = clamp01(state.mood_stability + float(mood.get("stability", 0) or 0))
    state.mood_anxiety = clamp01(state.mood_anxiety + float(mood.get("anxiety", 0) or 0))
    state.mood_loneliness = clamp01(state.mood_loneliness + float(mood.get("loneliness", 0) or 0))

    state.relation_mother = clamp01(state.relation_mother + float(relations.get("mother", 0) or 0))
    state.relation_friends = clamp01(state.relation_friends + float(relations.get("friends", 0) or 0))
    state.relation_work = clamp01(state.relation_work + float(relations.get("work", 0) or 0))
    state.relation_institution = clamp01(
        state.relation_institution + float(relations.get("institution", 0) or 0)
    )

    db.add(state)
    db.commit()
    ensure_state_driven_events(db, user, state)


def _resolve_event_by_key(db: Session, user: User, event_key: str) -> None:
    event = db.scalar(
        select(PlayerWorldEvent).where(
            PlayerWorldEvent.user_id == user.id,
            PlayerWorldEvent.event_key == event_key,
            PlayerWorldEvent.status == "active",
        )
    )
    if not event:
        return

    event.status = "resolved"
    db.add(event)
    db.commit()


def _build_world_journal(state: PlayerWorldState, events: list[PlayerWorldEvent]) -> list[dict]:
    journal = [
        {
            "id": "journal-phase",
            "label": "当前阶段",
            "text": f"人生阶段已进入 {state.phase_key}，世界状态与剧情会共同推进后续内容。",
        }
    ]
    if events:
        journal.append(
            {
                "id": "journal-event",
                "label": "焦点事件",
                "text": f"当前最值得关注的是「{events[0].title}」。",
            }
        )
    return journal[:3]
