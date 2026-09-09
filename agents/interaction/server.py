"""Internal reviewed-template renderer. No public network or model dependency."""

import re
from typing import Any

from flask import Flask, jsonify, request

from she_engine.learning_render import (
    PROMPT_CONTEXT,
    REVIEWED_STORY_ACTIONS,
    RPG_CONTENT_IDS,
    RPG_NODES,
    RPG_PHASES,
    RPG_PROMPT_IDS,
    RPG_WORLD_ROLES,
    TARGET_EXPRESSIONS,
    TEACHING_ACTIONS,
    render,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32768

_ACTION_FIELDS = frozenset(
    {
        "action_id",
        "prompt_id",
        "feedback_id",
        "node_id",
        "phase",
        "world_role",
        "learning_goal",
        "target_expression",
        "language_level",
        "scaffold_level",
        "teaching_action",
        "correction_policy",
        "story_action",
        "success_condition",
        "memory_policy",
    }
)
_REQUIRED_FIELDS = frozenset(
    {
        "learning_goal",
        "target_expression",
        "language_level",
        "scaffold_level",
        "teaching_action",
        "correction_policy",
        "story_action",
        "success_condition",
        "memory_policy",
    }
)
_CORRECTION_POLICIES = frozenset({"recast", "ignore", "explicit_later"})
_MEMORY_POLICIES = frozenset({"no_write", "candidate", "confirmed"})
_ACTION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


def _optional_enum(action: dict[str, Any], field: str, allowed: frozenset[str]) -> bool:
    return field not in action or (type(action[field]) is str and action[field] in allowed)


def _valid_success_condition(value: Any, target_expression: str) -> bool:
    if type(value) is not dict:
        return False
    if set(value) == {"contains", "intelligible"}:
        return (
            value["contains"] == target_expression
            and value["contains"] in TARGET_EXPRESSIONS
            and type(value["intelligible"]) is bool
        )
    if set(value) == {"quest_completed"}:
        return value["quest_completed"] is True and target_expression == "Our picnic is ready."
    if set(value) != {"criterion_id", "act", "slots"} or type(value["slots"]) is not dict:
        return False
    criterion = (value["criterion_id"], value["act"], value["slots"])
    expected = {
        "I want milk.": ("request_milk.v1", "request_item", {"item": "milk"}),
        "I choose the red cup.": (
            "select_red_cup.v1",
            "select_item",
            {"item": "cup", "color": "red"},
        ),
    }
    return criterion == expected.get(target_expression)


def _valid_action(action: Any) -> bool:
    if type(action) is not dict:
        return False
    fields = set(action)
    if not _REQUIRED_FIELDS <= fields or not fields <= _ACTION_FIELDS:
        return False
    if (
        type(action["target_expression"]) is not str
        or action["target_expression"] not in TARGET_EXPRESSIONS
    ):
        return False
    if type(action["scaffold_level"]) is not int or not 0 <= action["scaffold_level"] <= 6:
        return False
    if type(action["teaching_action"]) is not str or action["teaching_action"] not in TEACHING_ACTIONS:
        return False

    if "action_id" in action and (
        type(action["action_id"]) is not str or _ACTION_ID_RE.fullmatch(action["action_id"]) is None
    ):
        return False
    if "learning_goal" in action and (
        type(action["learning_goal"]) is not str
        or not action["learning_goal"].strip()
        or len(action["learning_goal"]) > 240
    ):
        return False
    if "language_level" in action and (
        type(action["language_level"]) is not int or not 0 <= action["language_level"] <= 5
    ):
        return False
    if not _optional_enum(action, "prompt_id", RPG_PROMPT_IDS):
        return False
    if not _optional_enum(action, "feedback_id", RPG_CONTENT_IDS):
        return False
    if not _optional_enum(action, "node_id", RPG_NODES):
        return False
    if not _optional_enum(action, "phase", RPG_PHASES):
        return False
    if not _optional_enum(action, "world_role", RPG_WORLD_ROLES):
        return False
    if not _optional_enum(action, "correction_policy", _CORRECTION_POLICIES):
        return False
    if not _optional_enum(action, "story_action", REVIEWED_STORY_ACTIONS):
        return False
    if not _optional_enum(action, "memory_policy", _MEMORY_POLICIES):
        return False
    if "success_condition" in action and not _valid_success_condition(
        action["success_condition"], action["target_expression"]
    ):
        return False

    story_action = action.get("story_action")
    feedback_id = action.get("feedback_id")
    if type(story_action) is str and story_action.startswith("rpg:"):
        if feedback_id is None or story_action != f"rpg:{feedback_id}":
            return False
    if "prompt_id" in action and PROMPT_CONTEXT[action["prompt_id"]][1] != action["scaffold_level"]:
        return False
    if feedback_id in RPG_PROMPT_IDS and (
        action.get("prompt_id") != feedback_id
        or action["teaching_action"] not in {"ask", "prompt", "reinvite"}
    ):
        return False
    return True


@app.get("/healthz")
def health():
    return jsonify(ok=True)


@app.post("/interaction/render")
def learning_render():
    action = request.get_json(silent=True)
    if not _valid_action(action):
        return jsonify(error="invalid_action"), 400
    return jsonify(text=render(action), source="reviewed_template")
