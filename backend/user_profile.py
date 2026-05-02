from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
PROFILE_PATH = Path(os.environ.get("EUREKA_PROFILE_PATH", DATA_DIR / "user_profiles.json"))

DEFAULT_USER_ID = "default"
SKILL_LEVELS = ("beginner", "intermediate", "advanced")


def _empty_profile(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "lessons_completed": [],
        "quiz_scores": {},
        "time_spent_per_lesson": {},
        "retries_per_quiz": {},
        "skipped_sections": [],
        "skill_levels": {},
        "recent_mistakes": [],
        "solutions": [],
        "attempt_history": [],
        "updated_at": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_all_profiles() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        return {}

    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            data = json.load(profile_file)
    except (json.JSONDecodeError, OSError):
        return {}

    return data if isinstance(data, dict) else {}


def _save_all_profiles(profiles: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PROFILE_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as profile_file:
        json.dump(profiles, profile_file, indent=2, sort_keys=True)
    tmp_path.replace(PROFILE_PATH)


def get_profile(user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    profiles = _load_all_profiles()
    profile = profiles.get(user_id) or _empty_profile(user_id)
    return _normalize_profile(profile, user_id)


def get_user_state(user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    profile = get_profile(user_id)
    return {
        "profile": profile,
        "pace": calculate_pace(profile),
        "recommendations": build_recommendations(profile),
        "adaptive_hint": build_adaptive_hint(profile),
    }


def update_progress(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("user_id") or DEFAULT_USER_ID)
    topic = str(payload.get("topic") or payload.get("section") or "general").strip() or "general"
    lesson_id = str(payload.get("lesson_id") or topic)
    quiz_id = str(payload.get("quiz_id") or lesson_id)

    profiles = _load_all_profiles()
    profile = _normalize_profile(profiles.get(user_id) or _empty_profile(user_id), user_id)

    if payload.get("completed") is True and lesson_id not in profile["lessons_completed"]:
        profile["lessons_completed"].append(lesson_id)

    if payload.get("skipped") is True and lesson_id not in profile["skipped_sections"]:
        profile["skipped_sections"].append(lesson_id)

    if "time_spent_seconds" in payload:
        profile["time_spent_per_lesson"][lesson_id] = (
            int(profile["time_spent_per_lesson"].get(lesson_id, 0))
            + max(0, _safe_int(payload.get("time_spent_seconds")))
        )

    retries = max(0, _safe_int(payload.get("retries", 0)))
    if retries:
        profile["retries_per_quiz"][quiz_id] = (
            int(profile["retries_per_quiz"].get(quiz_id, 0)) + retries
        )

    score = payload.get("quiz_score")
    if score is not None:
        score_value = max(0, min(100, _safe_int(score)))
        profile["quiz_scores"].setdefault(topic, []).append(
            {"score": score_value, "retries": retries, "lesson_id": lesson_id, "at": _now()}
        )
        profile["skill_levels"][topic] = calculate_skill_level(score_value, retries)

    mistakes = payload.get("mistakes") or []
    if isinstance(mistakes, str):
        mistakes = [mistakes]
    for mistake in mistakes:
        mistake_text = str(mistake).strip()
        if mistake_text:
            profile["recent_mistakes"].append(
                {"topic": topic, "mistake": mistake_text, "lesson_id": lesson_id, "at": _now()}
            )
    profile["recent_mistakes"] = profile["recent_mistakes"][-12:]

    if "solution" in payload:
        profile["solutions"].append(
            {"lesson_id": lesson_id, "topic": topic, "solution": str(payload["solution"]), "at": _now()}
        )
        profile["solutions"] = profile["solutions"][-25:]

    if "attempt" in payload:
        profile["attempt_history"].append(
            {"lesson_id": lesson_id, "topic": topic, "attempt": str(payload["attempt"]), "at": _now()}
        )
        profile["attempt_history"] = profile["attempt_history"][-50:]

    profile["updated_at"] = _now()
    profiles[user_id] = profile
    _save_all_profiles(profiles)

    return {
        "profile": profile,
        "updated_skill_level": profile["skill_levels"].get(topic, "beginner"),
        "pace": calculate_pace(profile),
        "recommendations": build_recommendations(profile, topic),
        "adaptive_hint": build_adaptive_hint(profile, topic),
    }


def calculate_skill_level(score: int, retries: int) -> str:
    if score >= 85 and retries <= 1:
        return "advanced"
    if score >= 65 and retries <= 3:
        return "intermediate"
    return "beginner"


def calculate_pace(profile: dict[str, Any]) -> str:
    times = [int(value) for value in profile["time_spent_per_lesson"].values() if int(value) > 0]
    retry_total = sum(int(value) for value in profile["retries_per_quiz"].values())

    if not times:
        return "steady learner"

    average_seconds = sum(times) / len(times)
    if average_seconds <= 180 and retry_total <= max(1, len(times)):
        return "fast learner"
    if average_seconds >= 600 or retry_total >= len(times) * 3:
        return "slow learner"
    return "steady learner"


def build_recommendations(profile: dict[str, Any], current_topic: str | None = None) -> list[str]:
    weak_topics = [
        topic for topic, level in profile["skill_levels"].items() if level == "beginner"
    ]
    if current_topic and profile["skill_levels"].get(current_topic) == "beginner":
        return [f"Review the basics of {current_topic} before moving on."]
    if weak_topics:
        return [f"Practice {weak_topics[-1]} with a short challenge block next."]
    if profile["skill_levels"]:
        return ["Move to a harder lesson or ask for an advanced variation."]
    return ["Start with the next lesson and take the first section quiz."]


def build_adaptive_hint(profile: dict[str, Any], current_topic: str | None = None) -> str:
    mistakes = profile.get("recent_mistakes", [])
    if current_topic:
        topic_mistakes = [m for m in mistakes if m.get("topic") == current_topic]
        if topic_mistakes:
            return f"You struggled with {current_topic}, reviewing basics before increasing difficulty."

    if mistakes:
        topic = mistakes[-1].get("topic", "this topic")
        return f"You struggled with {topic}, so explanations will slow down and use targeted examples."

    if profile.get("skill_levels") and all(
        level == "advanced" for level in profile["skill_levels"].values()
    ):
        return "You are performing well, so new explanations can include tougher examples."

    return "Your course will adapt as you complete quizzes and practice blocks."


def ai_learning_context(user_id: str, topic: str) -> dict[str, Any]:
    state = get_user_state(user_id)
    profile = state["profile"]
    mistakes = [
        item["mistake"]
        for item in profile.get("recent_mistakes", [])
        if item.get("topic") == topic
    ][-3:]

    return {
        "skill_level": profile.get("skill_levels", {}).get(topic, "beginner"),
        "recent_mistakes": mistakes,
        "pace": state["pace"],
        "recommendations": state["recommendations"],
    }


def _normalize_profile(profile: dict[str, Any], user_id: str) -> dict[str, Any]:
    normalized = deepcopy(_empty_profile(user_id))
    if isinstance(profile, dict):
        normalized.update(profile)
    normalized["user_id"] = user_id
    for key in (
        "lessons_completed",
        "skipped_sections",
        "recent_mistakes",
        "solutions",
        "attempt_history",
    ):
        if not isinstance(normalized.get(key), list):
            normalized[key] = []
    for key in ("quiz_scores", "time_spent_per_lesson", "retries_per_quiz", "skill_levels"):
        if not isinstance(normalized.get(key), dict):
            normalized[key] = {}
    return normalized


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
