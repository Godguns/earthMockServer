from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.models.persona import PersonaProfile
from app.models.user import User


@dataclass(frozen=True)
class NpcProfile:
    key: str
    display_name: str
    conversation_key: str
    relation: str
    tone_guide: str
    proactive_rules: str
    dify_api_key: str | None
    workflow_id: str | None = None


MOTHER_NPC_PROFILE = NpcProfile(
    key="mother",
    display_name="妈妈",
    conversation_key="npc:mother",
    relation="player_mother",
    tone_guide=(
        "你是中国式母亲。你关心孩子的吃饭、睡眠、工作、存款和未来。"
        "你说话会带一点唠叨、操心、催促和隐性的期待，但底色是爱，不是恶意。"
        "你不说空洞大道理，更像微信里会发来的真实短消息。"
    ),
    proactive_rules=(
        "主动消息必须短，通常 1 到 3 句。"
        "优先结合时间、天气、最近一次聊天内容和孩子当前压力。"
        "不要每次都说教，可以有问候、叮嘱、提醒、打听近况、催休息或催工作。"
    ),
    dify_api_key=settings.dify_npc_mother_api_key,
    workflow_id=settings.dify_npc_mother_workflow_id,
)


def get_npc_profile(npc_key: str) -> NpcProfile:
    if npc_key == MOTHER_NPC_PROFILE.key:
        return MOTHER_NPC_PROFILE
    raise KeyError(f"Unknown NPC key: {npc_key}")


def build_mother_dify_inputs(
    persona: PersonaProfile,
    user: User,
    *,
    trigger_type: str,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    runtime = runtime_context or {}
    raw_settings = persona.raw_settings if isinstance(persona.raw_settings, dict) else {}
    identity = raw_settings.get("identity") or {}
    anchors = raw_settings.get("anchors") or {}
    raw_answers = raw_settings.get("rawAnswers") or {}
    origin = anchors.get("origin") or {}
    body = anchors.get("body") or {}
    soul = anchors.get("soul") or {}
    love = anchors.get("love") or {}
    finance = anchors.get("finance") or {}

    birth_date = str(identity.get("birthDate") or "")
    birth_year = birth_date.split("-", 1)[0] if birth_date and birth_date != "未标定" else ""

    payload = {
        "player_name": _coalesce(identity.get("name"), persona.display_name, user.username),
        "player_birth_year": _coalesce(runtime.get("player_birth_year"), birth_year),
        "player_birthplace": _coalesce(origin.get("birthplace")),
        "family_type": _coalesce(origin.get("familyType")),
        "family_expectation": _coalesce(origin.get("familyExpectation")),
        "childhood_label": _coalesce(raw_answers.get("childhoodFeedback")),
        "parent_similarity": _coalesce(raw_answers.get("similarToParents")),
        "home_meaning": _coalesce(raw_answers.get("meaningOfHome")),
        "parent_marriage_influence": _coalesce(raw_answers.get("parentsMarriageImpact")),
        "current_career": _coalesce(runtime.get("current_career"), identity.get("careerStatus")),
        "current_money": _coalesce(runtime.get("current_money"), finance.get("savings")),
        "current_stress": _coalesce(runtime.get("current_stress"), "unknown"),
        "current_vitality": _coalesce(runtime.get("current_vitality"), body.get("feedback")),
        "current_relationship_status": _coalesce(
            runtime.get("current_relationship_status"),
            love.get("status"),
        ),
        "player_fear": _coalesce(soul.get("fear")),
        "player_desire": _coalesce(soul.get("desire")),
        "player_life_philosophy": _coalesce(soul.get("priority")),
        "player_believe_aliens": _coalesce(raw_answers.get("alienBelief")),
        "player_love_fear": _coalesce(raw_answers.get("loveFear")),
        "trigger_type": _coalesce(trigger_type),
        "game_time": _coalesce(
            runtime.get("game_time"),
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        ),
        "game_day_of_week": _coalesce(runtime.get("game_day_of_week"), "unknown"),
        "days_since_last_chat": _coalesce(runtime.get("days_since_last_chat"), "unknown"),
        "last_chat_summary": _coalesce(runtime.get("last_chat_summary"), "暂无聊天记录"),
    }
    return {
        "raw_inputs": json.dumps(payload, ensure_ascii=False),
        **payload,
    }


def build_mother_reply_query(player_message: str) -> str:
    return (
        "请你以妈妈的身份回复孩子刚发来的消息。"
        "回复要像真实微信聊天，不要写成长段说教。"
        f"孩子刚刚说：{player_message}"
    )


def build_mother_proactive_query(
    trigger_type: str,
    runtime_context: dict[str, Any] | None = None,
) -> str:
    runtime = runtime_context or {}
    event_hint = runtime.get("event_hint") or "请根据当前情境，主动给孩子发一条消息。"
    return (
        "请你以妈妈的身份，决定现在要不要主动发消息给孩子。"
        "如果适合，就发一条自然、克制、真实的短消息。"
        "不要写解释，不要分点。"
        f"触发类型：{trigger_type}。"
        f"情境补充：{event_hint}"
    )


def _coalesce(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return ""
