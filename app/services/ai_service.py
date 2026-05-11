from __future__ import annotations

import random

from app.models.persona import PersonaProfile


class NarrativeAIService:
    """A lightweight placeholder AI layer that can later be swapped for an LLM provider."""

    ambient_templates = [
        "{speaker}刚刚路过，想起了你提过的{topic}，随手发来一句问候。",
        "{speaker}今天状态有点{mood}，第一时间想到的是和你聊聊{topic}。",
        "{speaker}在这个世界里又经历了一点小事，觉得你会想知道。",
    ]
    event_templates = [
        "{speaker}注意到事件“{trigger}”已经发生，觉得这会影响你们接下来的关系走向。",
        "{speaker}对“{trigger}”这件事反应很强烈，忍不住来找你说两句。",
    ]

    @classmethod
    def build_random_npc_message(cls, persona: PersonaProfile) -> dict[str, str]:
        speaker = persona.display_name or persona.archetype or "某位NPC"
        topic = random.choice(persona.favorite_topics or ["今天的生活"])
        mood = random.choice(persona.emotional_traits or ["微妙"])
        opening = random.choice(cls.ambient_templates).format(
            speaker=speaker,
            topic=topic,
            mood=mood,
        )
        detail = persona.communication_style or "他说话的节奏自然、带一点真实生活感。"
        title = f"{speaker}发来了一条新消息"
        content = f"{opening} {detail}"
        return {"title": title, "content": content, "speaker": speaker}

    @classmethod
    def build_event_message(
        cls,
        persona: PersonaProfile | None,
        trigger_name: str,
        fallback_content: str,
    ) -> dict[str, str]:
        speaker = "系统"
        if persona and (persona.display_name or persona.archetype):
            speaker = persona.display_name or persona.archetype or "系统"
        opening = random.choice(cls.event_templates).format(speaker=speaker, trigger=trigger_name)
        return {
            "title": f"{trigger_name}事件更新",
            "content": f"{opening} {fallback_content}",
            "speaker": speaker,
        }

