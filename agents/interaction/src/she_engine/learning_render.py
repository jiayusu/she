"""Render finite, reviewed learning and RPG actions in the voice of Xiao P.

The renderer never interpolates values supplied by a caller. Every value that can
affect child-facing text is resolved through a reviewed enum table first, and every
result (including the fallback) passes through :class:`LocalSafetyFilter`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .safety import LocalSafetyFilter


SAFE_FALLBACK = "Let's look around together."

TEACHING_ACTIONS = frozenset(
    {"ask", "prompt", "reinvite", "recast", "advance_story", "explore", "pause"}
)
RPG_NODES = frozenset({"collect_milk", "find_red_cup", "picnic_ready"})
RPG_PHASES = frozenset(
    {
        "seeking_object",
        "confirming_object",
        "presenting",
        "awaiting_speech",
        "resolving",
        "paused",
        "delivery_failed",
        "completed",
    }
)
RPG_WORLD_ROLES = frozenset({"饮品保管员", "杯子管理员", "野餐向导"})
RPG_FEEDBACK_IDS = frozenset(
    {
        "milk_ready",
        "milk_help",
        "red_cup_ready",
        "red_cup_help",
        "picnic_complete",
        "picnic_pause",
    }
)

PROMPT_CONTEXT: dict[str, tuple[str, int]] = {
    **{f"collect_milk_s{level}": ("collect_milk", level) for level in range(7)},
    **{f"find_red_cup_s{level}": ("find_red_cup", level) for level in range(7)},
    **{f"picnic_ready_s{level}": ("picnic_ready", level) for level in range(7)},
}
RPG_PROMPT_IDS = frozenset(PROMPT_CONTEXT)

_FEEDBACK_FROM_STORY_ACTION = {
    f"rpg:{feedback_id}": feedback_id for feedback_id in RPG_FEEDBACK_IDS
}
_LEGACY_STORY_SCENE = {
    "world_waits_for_milk": "collect_milk",
    "world_waits_for_water": "request_water",
    "world_waits_for_apples": "like_apples",
    "world_waits_for_please": "open_please",
}
_NEUTRAL_STORY_ACTIONS = frozenset({"pause_and_offer_comfort"})
REVIEWED_STORY_ACTIONS = frozenset(
    {*_FEEDBACK_FROM_STORY_ACTION, *_LEGACY_STORY_SCENE, *_NEUTRAL_STORY_ACTIONS}
)

# Kept as a public constant for existing callers. Each tuple is
# (choice prompt, sentence starter, complete model).
PROMPTS = {
    "I want milk.": ("Milk or water?", "I want...", "I want milk."),
    "I want water.": ("Water or milk?", "I want...", "I want water."),
    "I like apples.": ("Apples or bananas?", "I like...", "I like apples."),
    "Open, please.": ("Open or close?", "Open...", "Open, please."),
    "I choose the red cup.": (
        "Red cup or blue cup?",
        "I choose...",
        "I choose the red cup.",
    ),
    "Our picnic is ready.": (
        "Ready or not yet?",
        "Our picnic...",
        "Our picnic is ready.",
    ),
}
TARGET_EXPRESSIONS = frozenset(PROMPTS)

_SCENE_BY_TARGET = {
    "I want milk.": "collect_milk",
    "I want water.": "request_water",
    "I like apples.": "like_apples",
    "Open, please.": "open_please",
    "I choose the red cup.": "find_red_cup",
    "Our picnic is ready.": "picnic_ready",
}
_SCENE_BY_NODE = {node: node for node in RPG_NODES}
_SCENE_BY_ROLE = {
    "饮品保管员": "collect_milk",
    "杯子管理员": "find_red_cup",
    "野餐向导": "picnic_ready",
}
_SCENE_BY_FEEDBACK = {
    "milk_ready": "collect_milk",
    "milk_help": "collect_milk",
    "red_cup_ready": "find_red_cup",
    "red_cup_help": "find_red_cup",
    "picnic_complete": "picnic_ready",
    "picnic_pause": "picnic_ready",
}

# Complete, reviewed rows make scaffold selection a lookup rather than string
# composition. S6 is always listening-only participation.
_RPG_SCAFFOLDED_COPY = {
    "collect_milk": {
        "ask": (
            "The drink keeper needs our words. What should we ask for?",
            "The drink keeper is listening. What do we need?",
            "The drink keeper asks: Milk or water?",
            "The drink keeper is listening: I want...",
            "Try: I want milk.",
            "Say it with me: I want milk.",
            "Just listen: I want milk.",
        ),
        "prompt": (
            "The drink keeper is still listening. Try once more.",
            "We need milk. What can we say?",
            "Milk or water? Let's choose.",
            "Try this start: I want...",
            "You can say: I want milk.",
            "Let's say it together: I want milk.",
            "Let's listen together: I want milk.",
        ),
    },
    "find_red_cup": {
        "ask": (
            "The cup keeper needs our choice. Which cup should we pick?",
            "Which cup does our picnic need?",
            "The cup keeper asks: Red cup or blue cup?",
            "The cup keeper is listening: I choose...",
            "Try: I choose the red cup.",
            "Say it with me: I choose the red cup.",
            "Just listen: I choose the red cup.",
        ),
        "prompt": (
            "The cup keeper is still listening. Try once more.",
            "We need the red cup. Which one will you choose?",
            "Red cup or blue cup? Let's choose.",
            "Try this start: I choose...",
            "You can say: I choose the red cup.",
            "Let's say it together: I choose the red cup.",
            "Let's listen together: I choose the red cup.",
        ),
    },
    "picnic_ready": {
        "ask": (
            "The picnic guide says our pretend picnic is ready.",
            "The picnic guide says our pretend picnic is ready.",
            "The picnic guide says our pretend picnic is ready.",
            "The picnic guide says: Our picnic...",
            "The picnic guide says: Our picnic is ready.",
            "Say it with me: Our picnic is ready.",
            "Just listen: Our picnic is ready.",
        ),
        "prompt": (
            "The picnic guide has a happy message for us.",
            "Our pretend picnic is ready.",
            "Ready or not yet? Our picnic is ready.",
            "Let's listen: Our picnic...",
            "Let's listen: Our picnic is ready.",
            "Let's say it together: Our picnic is ready.",
            "Let's listen together: Our picnic is ready.",
        ),
    },
}

_RPG_FIXED_COPY = {
    "collect_milk": {
        "reinvite": "The drink keeper is listening. Would you like to try again?",
        "recast": "I want milk. The drink keeper heard us.",
        "advance_story": "Milk is ready. Find a cup!",
        "explore": "Let's find the drink keeper by the fridge.",
        "pause": "The drink keeper can wait. Let's take a little break.",
    },
    "find_red_cup": {
        "reinvite": "The cup keeper is listening. Would you like to try again?",
        "recast": "I choose the red cup. The cup keeper heard us.",
        "advance_story": "Red cup! Our picnic is ready!",
        "explore": "Let's look for the red cup by the table.",
        "pause": "The cup keeper can wait. Let's take a little break.",
    },
    "picnic_ready": {
        "reinvite": "The picnic guide can wait. Listen when you're ready.",
        "recast": "Our picnic is ready. What a lovely ending!",
        "advance_story": "Our picnic is ready. We did it!",
        "explore": "Our pretend picnic is ready. Let's look for a new adventure.",
        "pause": "The picnic can wait. Let's take a little break.",
    },
}

_SUCCESS_FEEDBACK_COPY = {
    "milk_ready": "Milk is ready. Find a cup!",
    "red_cup_ready": "Red cup! Our picnic is ready!",
    "picnic_complete": "Our picnic is ready. We did it!",
}

_GENERIC_PROMPT_COPY = {
    "I want milk.": (
        "Let's try once more.",
        "What do we want to drink?",
        "Milk or water? Let's choose.",
        "Try this start: I want...",
        "You can say: I want milk.",
        "Let's say it together: I want milk.",
        "Just listen with me: I want milk.",
    ),
    "I want water.": (
        "Let's try once more.",
        "What do we want to drink?",
        "Water or milk? Let's choose.",
        "Try this start: I want...",
        "You can say: I want water.",
        "Let's say it together: I want water.",
        "Just listen with me: I want water.",
    ),
    "I like apples.": (
        "Let's try once more.",
        "Which fruit do we like?",
        "Apples or bananas? Let's choose.",
        "Try this start: I like...",
        "You can say: I like apples.",
        "Let's say it together: I like apples.",
        "Just listen with me: I like apples.",
    ),
    "Open, please.": (
        "Let's try once more.",
        "What polite word can help?",
        "Open or close? Let's choose.",
        "Try this start: Open...",
        "You can say: Open, please.",
        "Let's say it together: Open, please.",
        "Just listen with me: Open, please.",
    ),
    "I choose the red cup.": (
        "Let's try once more.",
        "Which cup do we choose?",
        "Red cup or blue cup? Let's choose.",
        "Try this start: I choose...",
        "You can say: I choose the red cup.",
        "Let's say it together: I choose the red cup.",
        "Just listen with me: I choose the red cup.",
    ),
    "Our picnic is ready.": (
        "Let's listen to the ending.",
        "Our pretend picnic is ready.",
        "Ready or not yet? Our picnic is ready.",
        "Let's listen: Our picnic...",
        "Let's listen: Our picnic is ready.",
        "Let's say it together: Our picnic is ready.",
        "Just listen with me: Our picnic is ready.",
    ),
}

_GENERIC_FIXED_COPY = {
    "I want milk.": {
        "recast": "I want milk. Me too!",
        "advance_story": "Nice asking! Milk is ready.",
        "explore": "Let's look for the milk clue.",
    },
    "I want water.": {
        "recast": "I want water. Me too!",
        "advance_story": "Nice asking! Water is ready.",
        "explore": "Let's look for the water clue.",
    },
    "I like apples.": {
        "recast": "I like apples. They are tasty!",
        "advance_story": "The story heard your apple choice!",
        "explore": "Let's look for an apple clue.",
    },
    "Open, please.": {
        "recast": "Open, please. That sounds kind!",
        "advance_story": "Your polite words opened the next story step!",
        "explore": "Let's look for something that can open.",
    },
    "I choose the red cup.": {
        "recast": "I choose the red cup. Great choice!",
        "advance_story": "Red cup! Our picnic is ready!",
        "explore": "Let's look for the red cup.",
    },
    "Our picnic is ready.": {
        "recast": "Our picnic is ready. What a lovely ending!",
        "advance_story": "Our picnic is ready. We did it!",
        "explore": "Let's look for a new adventure.",
    },
}


def _safe_text(text: str) -> str:
    safety = LocalSafetyFilter()
    ok, filtered = safety.filter(text, context="invite")
    if ok:
        return filtered
    fallback_ok, fallback = safety.filter(SAFE_FALLBACK, context="invite")
    return fallback if fallback_ok else SAFE_FALLBACK


def _known_string(
    action: Mapping[str, Any], field: str, allowed: set[str] | frozenset[str]
) -> bool:
    value = action.get(field)
    return value is None or (type(value) is str and value in allowed)


def _resolve_context(action: Mapping[str, Any]) -> tuple[str | None, str | None, bool]:
    """Return (scene, feedback_id, is_rpg) or mark an unsafe context as invalid."""

    if not _known_string(action, "target_expression", TARGET_EXPRESSIONS):
        return None, None, False
    if not _known_string(action, "node_id", RPG_NODES):
        return None, None, False
    if not _known_string(action, "world_role", RPG_WORLD_ROLES):
        return None, None, False
    if not _known_string(action, "prompt_id", RPG_PROMPT_IDS):
        return None, None, False
    if not _known_string(action, "feedback_id", RPG_FEEDBACK_IDS):
        return None, None, False
    if not _known_string(action, "phase", RPG_PHASES):
        return None, None, False
    if not _known_string(action, "story_action", REVIEWED_STORY_ACTIONS):
        return None, None, False

    scenes: set[str] = set()
    target = action.get("target_expression")
    if target is not None:
        scenes.add(_SCENE_BY_TARGET[target])
    node = action.get("node_id")
    if node is not None:
        scenes.add(_SCENE_BY_NODE[node])
    role = action.get("world_role")
    if role is not None:
        scenes.add(_SCENE_BY_ROLE[role])
    prompt_id = action.get("prompt_id")
    if prompt_id is not None:
        scenes.add(PROMPT_CONTEXT[prompt_id][0])

    story_action = action.get("story_action")
    if story_action in _LEGACY_STORY_SCENE:
        scenes.add(_LEGACY_STORY_SCENE[story_action])

    feedback_id = action.get("feedback_id")
    action_feedback = _FEEDBACK_FROM_STORY_ACTION.get(story_action)
    if action_feedback is not None:
        if feedback_id is not None and feedback_id != action_feedback:
            return None, None, False
        feedback_id = action_feedback

    if len(scenes) > 1:
        return None, None, False
    if not scenes and feedback_id is not None:
        scenes.add(_SCENE_BY_FEEDBACK[feedback_id])

    is_rpg = any(
        field in action
        for field in ("node_id", "phase", "world_role", "prompt_id", "feedback_id")
    ) or action_feedback is not None
    return (next(iter(scenes)) if scenes else None), feedback_id, is_rpg


def _render_generic(target: str, kind: str, level: int) -> str:
    if kind == "pause":
        return "Let's listen together. You can join in when you like."
    if kind == "reinvite":
        return "I'm listening. Would you like to try again?"
    if kind == "prompt":
        return _GENERIC_PROMPT_COPY[target][level]
    if kind in {"recast", "advance_story", "explore"}:
        return _GENERIC_FIXED_COPY[target][kind]

    choice, starter, model = PROMPTS[target]
    if level <= 2:
        return choice
    if level == 3:
        return starter
    if level <= 5:
        return model
    return _GENERIC_PROMPT_COPY[target][6]


def _render_rpg(scene: str, kind: str, level: int, feedback_id: str | None) -> str:
    if kind == "advance_story" and feedback_id in _SUCCESS_FEEDBACK_COPY:
        return _SUCCESS_FEEDBACK_COPY[feedback_id]
    if kind in {"ask", "prompt"}:
        return _RPG_SCAFFOLDED_COPY[scene][kind][level]
    return _RPG_FIXED_COPY[scene][kind]


def render(action: Mapping[str, Any] | Any) -> str:
    """Render one reviewed action and apply the final local safety filter.

    The HTTP boundary performs stricter shape validation. This function remains
    defensive for direct library callers: malformed or contradictory values produce
    the reviewed fallback and never become part of the output.
    """

    if not isinstance(action, Mapping):
        return _safe_text(SAFE_FALLBACK)

    kind = action.get("teaching_action")
    level = action.get("scaffold_level", 6)
    if (
        type(kind) is not str
        or kind not in TEACHING_ACTIONS
        or type(level) is not int
        or not 0 <= level <= 6
    ):
        return _safe_text(SAFE_FALLBACK)

    scene, feedback_id, is_rpg = _resolve_context(action)
    target = action.get("target_expression")
    if scene is None or target not in TARGET_EXPRESSIONS:
        return _safe_text(SAFE_FALLBACK)

    if is_rpg:
        if scene not in RPG_NODES:
            return _safe_text(SAFE_FALLBACK)
        text = _render_rpg(scene, kind, level, feedback_id)
    else:
        text = _render_generic(target, kind, level)
    return _safe_text(text)
