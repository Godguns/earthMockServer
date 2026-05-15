from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.story import StoryArc, StoryProgress
from app.models.user import User
from app.schemas.story import (
    StoryBranchOption,
    StoryChoice,
    StoryScenePayload,
    StoryStateRead,
)
from app.services.world_service import apply_story_world_effects


DEFAULT_ARC_KEY = "life_foundation"

STORY_BRANCHES: dict[str, dict] = {
    "campus_transition": {
        "label": "校园转场线",
        "description": "从学生身份过渡到真实社会的第一段人生主线。",
        "recommended_when": "career_contains_student",
        "start_scene_key": "campus_transition:intro",
        "scenes": {
            "campus_transition:intro": {
                "key": "campus_transition:intro",
                "title": "离开校园的那天",
                "scene_type": "dialogue",
                "background": "dormitory_exit",
                "music_cue": "slow_departure",
                "enter_effect": "cinematic-pan",
                "lines": [
                    {"speaker": "母亲", "text": "你不能一直停在那个阶段，现实会继续往前走。"},
                    {"speaker": "玩家", "text": "我知道，只是还没准备好。"},
                ],
                "choices": [
                    {
                        "key": "study",
                        "label": "继续学习",
                        "description": "延缓进入社会，但能先积累能力。",
                        "next_scene_key": "campus_transition:study_path",
                        "effect_key": "story_study",
                        "world_effects": {"mood": {"stability": 0.04}, "money": {"balance": -300}},
                    },
                    {
                        "key": "work",
                        "label": "直接工作",
                        "description": "更早接触社会压力，也更早获得现金流。",
                        "next_scene_key": "campus_transition:work_path",
                        "effect_key": "story_work",
                        "world_effects": {"money": {"balance": 300}, "mood": {"anxiety": 0.05}},
                    },
                ],
            },
            "campus_transition:study_path": {
                "key": "campus_transition:study_path",
                "title": "继续蓄力",
                "scene_type": "dialogue",
                "background": "library_twilight",
                "music_cue": "quiet_focus",
                "enter_effect": "soft-fade",
                "lines": [
                    {"speaker": "系统", "text": "你选择了暂缓冲刺现实，把时间换成能力。"},
                    {"speaker": "母亲", "text": "那就认真一点，不要只是为了逃避。"},
                ],
                "choices": [
                    {
                        "key": "accept",
                        "label": "继续前进",
                        "description": "主线进入能力积累期。",
                        "effect_key": "story_commit_study",
                    }
                ],
            },
            "campus_transition:work_path": {
                "key": "campus_transition:work_path",
                "title": "提前落地",
                "scene_type": "dialogue",
                "background": "city_bus_stop",
                "music_cue": "urban_hum",
                "enter_effect": "glitch-cut",
                "lines": [
                    {"speaker": "系统", "text": "你决定更快踏进社会，用结果检验自己。"},
                    {"speaker": "母亲", "text": "别硬扛，真撑不住要开口。"},
                ],
                "choices": [
                    {
                        "key": "accept",
                        "label": "迎接现实",
                        "description": "主线进入城市生存期。",
                        "effect_key": "story_commit_work",
                    }
                ],
            },
        },
    },
    "urban_pressure": {
        "label": "都市打工线",
        "description": "围绕房租、绩效、加班与城市关系展开的现实主线。",
        "recommended_when": "default",
        "start_scene_key": "urban_pressure:intro",
        "scenes": {
            "urban_pressure:intro": {
                "key": "urban_pressure:intro",
                "title": "城市第一晚",
                "scene_type": "dialogue",
                "background": "small_rental_room",
                "music_cue": "metro-night",
                "enter_effect": "signal-rise",
                "lines": [
                    {"speaker": "母亲", "text": "这个城市不会照顾你，得你自己学会活下去。"},
                    {"speaker": "玩家", "text": "那我就先撑过今晚。"},
                ],
                "choices": [
                    {
                        "key": "rent",
                        "label": "先找住处",
                        "description": "优先解决生存安全感。",
                        "next_scene_key": "urban_pressure:settle_room",
                        "effect_key": "story_rent_first",
                        "world_effects": {"money": {"balance": -600}, "mood": {"stability": 0.03}},
                    },
                    {
                        "key": "job",
                        "label": "先找工作",
                        "description": "优先解决现金流。",
                        "next_scene_key": "urban_pressure:chase_job",
                        "effect_key": "story_job_first",
                        "world_effects": {"money": {"balance": 200}, "mood": {"anxiety": 0.04}},
                    },
                ],
            },
            "urban_pressure:settle_room": {
                "key": "urban_pressure:settle_room",
                "title": "先有落脚点",
                "scene_type": "dialogue",
                "background": "window_after_rain",
                "music_cue": "safe-space",
                "enter_effect": "soft-fade",
                "lines": [
                    {"speaker": "系统", "text": "你先保住了今晚能睡在哪。"},
                    {"speaker": "玩家", "text": "至少我终于能把门关上。"},
                ],
                "choices": [
                    {
                        "key": "accept",
                        "label": "开始新生活",
                        "description": "主线进入城市安顿期。",
                        "effect_key": "story_room_secured",
                    }
                ],
            },
            "urban_pressure:chase_job": {
                "key": "urban_pressure:chase_job",
                "title": "先追现金流",
                "scene_type": "dialogue",
                "background": "office_lobby",
                "music_cue": "cold-elevator",
                "enter_effect": "flash-line",
                "lines": [
                    {"speaker": "系统", "text": "你把生存优先级压到了收入上。"},
                    {"speaker": "玩家", "text": "没钱的时候，其他事都像奢侈品。"},
                ],
                "choices": [
                    {
                        "key": "accept",
                        "label": "继续奔跑",
                        "description": "主线进入求职高压期。",
                        "effect_key": "story_income_priority",
                    }
                ],
            },
        },
    },
    "family_obligation": {
        "label": "家庭牵引线",
        "description": "围绕父母期待、照护责任与代际关系展开的人生主线。",
        "recommended_when": "family_present",
        "start_scene_key": "family_obligation:intro",
        "scenes": {
            "family_obligation:intro": {
                "key": "family_obligation:intro",
                "title": "来自家里的电话",
                "scene_type": "dialogue",
                "background": "phone_glow",
                "music_cue": "thin-distance",
                "enter_effect": "screen-iris",
                "lines": [
                    {"speaker": "母亲", "text": "家里不是要你立刻回来，只是很多事不能总靠我们扛。"},
                    {"speaker": "玩家", "text": "我明白，我只是还没找到平衡。"},
                ],
                "choices": [
                    {
                        "key": "return",
                        "label": "优先家庭",
                        "description": "更多时间放回家庭责任。",
                        "next_scene_key": "family_obligation:return_home",
                        "effect_key": "story_family_first",
                        "world_effects": {"relations": {"mother": 0.08}, "mood": {"stability": 0.03}},
                    },
                    {
                        "key": "persist",
                        "label": "坚持当前生活",
                        "description": "先守住自己的节奏。",
                        "next_scene_key": "family_obligation:hold_line",
                        "effect_key": "story_self_first",
                        "world_effects": {"relations": {"mother": -0.03}, "mood": {"anxiety": 0.03}},
                    },
                ],
            },
            "family_obligation:return_home": {
                "key": "family_obligation:return_home",
                "title": "把时间留给家里",
                "scene_type": "dialogue",
                "background": "station_return",
                "music_cue": "warm-recall",
                "enter_effect": "train-window",
                "lines": [
                    {"speaker": "系统", "text": "你把一部分人生推进权让给了家庭。"},
                ],
                "choices": [{"key": "accept", "label": "继续", "description": "进入家庭责任期。", "effect_key": "story_family_commit"}],
            },
            "family_obligation:hold_line": {
                "key": "family_obligation:hold_line",
                "title": "先保住自己",
                "scene_type": "dialogue",
                "background": "night_crossroad",
                "music_cue": "quiet-tension",
                "enter_effect": "glow-pulse",
                "lines": [
                    {"speaker": "系统", "text": "你选择继续向前，但这也会让关系进入拉扯。"},
                ],
                "choices": [{"key": "accept", "label": "继续", "description": "进入关系张力期。", "effect_key": "story_boundary_commit"}],
            },
        },
    },
    "career_breakthrough": {
        "label": "职业突破线",
        "description": "围绕技能成长、机会抉择与职业代价展开的主线。",
        "recommended_when": "career_focused",
        "start_scene_key": "career_breakthrough:intro",
        "scenes": {
            "career_breakthrough:intro": {
                "key": "career_breakthrough:intro",
                "title": "机会来到门口",
                "scene_type": "dialogue",
                "background": "meeting_room_blue",
                "music_cue": "tension-rise",
                "enter_effect": "focus-zoom",
                "lines": [
                    {"speaker": "系统", "text": "一个更陡的机会来到你面前，但代价也被同时摆上桌面。"},
                    {"speaker": "玩家", "text": "如果不抓，我可能会后悔。"},
                ],
                "choices": [
                    {
                        "key": "grab",
                        "label": "接住机会",
                        "description": "收入预期上升，但精力会被透支。",
                        "next_scene_key": "career_breakthrough:all_in",
                        "effect_key": "story_grab_chance",
                        "world_effects": {
                            "money": {"balance": 500},
                            "health": {"energy": -0.06},
                            "mood": {"stability": 0.03},
                        },
                    },
                    {
                        "key": "wait",
                        "label": "先稳住节奏",
                        "description": "保留恢复空间，但错失窗口风险上升。",
                        "next_scene_key": "career_breakthrough:stay_steady",
                        "effect_key": "story_wait_window",
                        "world_effects": {
                            "health": {"energy": 0.03},
                            "mood": {"anxiety": 0.02},
                        },
                    },
                ],
            },
            "career_breakthrough:all_in": {
                "key": "career_breakthrough:all_in",
                "title": "全力投入",
                "scene_type": "dialogue",
                "background": "office_midnight",
                "music_cue": "hard-clock",
                "enter_effect": "scanline",
                "lines": [
                    {"speaker": "系统", "text": "你决定在这个阶段，把更多人生筹码压向职业。"},
                ],
                "choices": [{"key": "accept", "label": "继续", "description": "进入高投入成长线。", "effect_key": "story_all_in_commit"}],
            },
            "career_breakthrough:stay_steady": {
                "key": "career_breakthrough:stay_steady",
                "title": "保留呼吸空间",
                "scene_type": "dialogue",
                "background": "cafe_evening",
                "music_cue": "slow-breath",
                "enter_effect": "soft-fade",
                "lines": [
                    {"speaker": "系统", "text": "你没有盲目冲刺，而是给自己保留了一段恢复区。"},
                ],
                "choices": [{"key": "accept", "label": "继续", "description": "进入稳态成长线。", "effect_key": "story_steady_commit"}],
            },
        },
    },
}


def ensure_default_story_arc(db: Session) -> StoryArc:
    arc = db.scalar(select(StoryArc).where(StoryArc.key == DEFAULT_ARC_KEY))
    if arc:
        return arc

    arc = StoryArc(
        key=DEFAULT_ARC_KEY,
        title="人生开场",
        summary="根据玩家人格与现实状态，选择一条更贴近人生处境的主线。",
        branching_rules={
            "default": {"branch_key": "urban_pressure"},
            "student": {"branch_key": "campus_transition"},
            "family": {"branch_key": "family_obligation"},
            "career": {"branch_key": "career_breakthrough"},
        },
        entry_conditions={},
    )
    db.add(arc)
    db.commit()
    db.refresh(arc)
    return arc


def get_or_create_story_progress(db: Session, user: User) -> StoryProgress:
    progress = db.scalar(select(StoryProgress).where(StoryProgress.user_id == user.id))
    if progress:
        return progress

    arc = ensure_default_story_arc(db)
    progress = StoryProgress(
        user_id=user.id,
        arc_key=arc.key,
        current_scene_key=None,
        branch_key=None,
        flags={"started": False, "scene_history": []},
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


def _persona_snapshot(persona) -> tuple[str, str, str]:
    raw = persona.raw_settings if isinstance(persona.raw_settings, dict) else {}
    identity = raw.get("identity") or {}
    anchors = raw.get("anchors") or {}
    career = str(identity.get("careerStatus") or "").strip()
    family_type = str((anchors.get("origin") or {}).get("familyType") or "").strip()
    archetype = str(persona.archetype or "").strip()
    return career, family_type, archetype


def list_branch_options(user: User, persona) -> list[dict]:
    career, family_type, archetype = _persona_snapshot(persona)

    preferred_key = choose_recommended_branch(persona)
    options: list[dict] = []
    for key, config in STORY_BRANCHES.items():
        recommended = key == preferred_key
        if key == "campus_transition" and "学生" not in f"{career} {archetype}":
            continue
        if key == "family_obligation" and not family_type:
            continue
        options.append(
            StoryBranchOption(
                key=key,
                label=config["label"],
                description=config["description"],
                start_scene_key=config["start_scene_key"],
                recommended=recommended,
            ).model_dump()
        )
    return options


def choose_recommended_branch(persona) -> str:
    career, family_type, archetype = _persona_snapshot(persona)
    combined = f"{career} {archetype}"

    if "学生" in combined:
        return "campus_transition"
    if family_type:
        return "family_obligation"
    if any(keyword in combined for keyword in ("职业", "事业", "工作", "成长")):
        return "career_breakthrough"
    return "urban_pressure"


def get_scene(branch_key: str, scene_key: str | None = None) -> StoryScenePayload | None:
    branch = STORY_BRANCHES.get(branch_key)
    if not branch:
        return None

    resolved_scene_key = scene_key or branch["start_scene_key"]
    scene = branch["scenes"].get(resolved_scene_key)
    if not scene:
        return None
    return StoryScenePayload.model_validate(scene)


def build_story_state(db: Session, user: User, persona) -> StoryStateRead:
    progress = get_or_create_story_progress(db, user)
    branches = [StoryBranchOption.model_validate(item) for item in list_branch_options(user, persona)]
    scene = get_scene(progress.branch_key, progress.current_scene_key) if progress.branch_key else None

    selected_choice = None
    last_choice_key = (progress.flags or {}).get("last_choice_key")
    if scene and last_choice_key:
        for choice in scene.choices:
            if choice.key == last_choice_key:
                selected_choice = choice
                break

    return StoryStateRead(
        progress=progress,
        branches=branches,
        scene=scene,
        selected_choice=selected_choice,
    )


def start_story_branch(db: Session, user: User, persona, branch_key: str) -> StoryStateRead:
    if branch_key not in STORY_BRANCHES:
        raise ValueError("Unknown story branch.")

    progress = get_or_create_story_progress(db, user)
    scene = get_scene(branch_key)
    if scene is None:
        raise ValueError("Story branch has no start scene.")

    flags = dict(progress.flags or {})
    flags["started"] = True
    flags["branch_started_at"] = datetime.now(UTC).isoformat()
    flags["last_choice_key"] = None
    flags["scene_history"] = [scene.key]

    progress.branch_key = branch_key
    progress.current_scene_key = scene.key
    progress.flags = flags
    progress.completed_at = None
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return build_story_state(db, user, persona)


def advance_story_choice(
    db: Session,
    user: User,
    persona,
    choice_key: str,
) -> StoryStateRead:
    progress = get_or_create_story_progress(db, user)
    if not progress.branch_key or not progress.current_scene_key:
        raise ValueError("Story has not started.")

    scene = get_scene(progress.branch_key, progress.current_scene_key)
    if scene is None:
        raise ValueError("Current story scene is missing.")

    choice = next((item for item in scene.choices if item.key == choice_key), None)
    if choice is None:
        raise ValueError("Story choice does not exist in current scene.")

    apply_story_world_effects(db, user, choice.world_effects)

    flags = dict(progress.flags or {})
    flags["last_choice_key"] = choice.key
    flags["last_choice_effect_key"] = choice.effect_key
    flags["last_choice_at"] = datetime.now(UTC).isoformat()

    next_scene_key = choice.next_scene_key
    if next_scene_key:
        next_scene = get_scene(progress.branch_key, next_scene_key)
        if next_scene is None:
            raise ValueError("Next story scene is missing.")
        progress.current_scene_key = next_scene.key
        history = list(flags.get("scene_history") or [])
        history.append(next_scene.key)
        flags["scene_history"] = history[-12:]
    else:
        progress.current_scene_key = None
        progress.completed_at = datetime.now(UTC)
        flags["scene_history"] = list(flags.get("scene_history") or [])

    progress.flags = flags
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return build_story_state(db, user, persona)


def build_proactive_story_hint(progress: StoryProgress | None) -> str | None:
    if not progress or not progress.branch_key:
        return None

    flags = progress.flags or {}
    last_choice_effect_key = flags.get("last_choice_effect_key")
    current_scene_key = progress.current_scene_key or ""
    branch_key = progress.branch_key

    if last_choice_effect_key:
        return f"story_branch={branch_key}; current_scene={current_scene_key}; last_effect={last_choice_effect_key}"
    return f"story_branch={branch_key}; current_scene={current_scene_key}"
