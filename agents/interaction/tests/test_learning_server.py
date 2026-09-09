import pytest

from server import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def _legacy_action():
    return {
        "learning_goal": "request a familiar object",
        "target_expression": "I want milk.",
        "language_level": 1,
        "scaffold_level": 2,
        "teaching_action": "ask",
        "correction_policy": "recast",
        "story_action": "world_waits_for_milk",
        "success_condition": {"contains": "I want milk.", "intelligible": True},
        "memory_policy": "no_write",
    }


def _rpg_action():
    return {
        "action_id": "action-002",
        "prompt_id": "find_red_cup_s2",
        "feedback_id": "milk_ready",
        "node_id": "find_red_cup",
        "phase": "seeking_object",
        "world_role": "杯子管理员",
        "learning_goal": "Select the red cup for the pretend picnic.",
        "target_expression": "I choose the red cup.",
        "language_level": 1,
        "scaffold_level": 2,
        "teaching_action": "advance_story",
        "correction_policy": "recast",
        "story_action": "rpg:milk_ready",
        "success_condition": {
            "criterion_id": "select_red_cup.v1",
            "act": "select_item",
            "slots": {"item": "cup", "color": "red"},
        },
        "memory_policy": "no_write",
    }


def _director_prompt_action(node="collect_milk", level=2, kind="ask"):
    contexts = {
        "collect_milk": {
            "learning_goal": "Request milk for the pretend picnic.",
            "target_expression": "I want milk.",
            "world_role": "饮品保管员",
            "success_condition": {
                "criterion_id": "request_milk.v1",
                "act": "request_item",
                "slots": {"item": "milk"},
            },
        },
        "find_red_cup": {
            "learning_goal": "Select the red cup for the pretend picnic.",
            "target_expression": "I choose the red cup.",
            "world_role": "杯子管理员",
            "success_condition": {
                "criterion_id": "select_red_cup.v1",
                "act": "select_item",
                "slots": {"item": "cup", "color": "red"},
            },
        },
        "picnic_ready": {
            "learning_goal": "Hear the story ending without another output demand.",
            "target_expression": "Our picnic is ready.",
            "world_role": "野餐向导",
            "success_condition": {"quest_completed": True},
        },
    }
    prompt_id = f"{node}_s{level}"
    context = contexts[node]
    return {
        "action_id": f"action-{node}-{level}",
        "prompt_id": prompt_id,
        "feedback_id": prompt_id,
        "node_id": node,
        "phase": "presenting",
        "world_role": context["world_role"],
        "learning_goal": context["learning_goal"],
        "target_expression": context["target_expression"],
        "language_level": 1,
        "scaffold_level": level,
        "teaching_action": kind,
        "correction_policy": "recast",
        "story_action": f"rpg:{prompt_id}",
        "success_condition": context["success_condition"],
        "memory_policy": "no_write",
    }


def test_render_endpoint_accepts_legacy_and_rpg_teaching_actions(client):
    legacy = client.post("/interaction/render", json=_legacy_action())
    assert legacy.status_code == 200
    assert legacy.get_json()["text"] == "Milk or water?"

    rpg = client.post("/interaction/render", json=_rpg_action())
    assert rpg.status_code == 200
    assert rpg.get_json()["text"] == "Milk is ready. Find a cup!"


@pytest.mark.parametrize(
    "node,level,expected",
    [
        ("collect_milk", 1, "The drink keeper is listening. What do we need?"),
        ("collect_milk", 2, "The drink keeper asks: Milk or water?"),
        ("collect_milk", 3, "The drink keeper is listening: I want..."),
        ("find_red_cup", 1, "Which cup does our picnic need?"),
        ("find_red_cup", 2, "The cup keeper asks: Red cup or blue cup?"),
        ("find_red_cup", 3, "The cup keeper is listening: I choose..."),
        ("picnic_ready", 1, "The picnic guide says our pretend picnic is ready."),
        ("picnic_ready", 2, "The picnic guide says our pretend picnic is ready."),
        ("picnic_ready", 3, "The picnic guide says: Our picnic..."),
    ],
)
def test_render_endpoint_accepts_director_prompt_content_ids(client, node, level, expected):
    response = client.post(
        "/interaction/render",
        json=_director_prompt_action(node=node, level=level),
    )
    assert response.status_code == 200
    assert response.get_json()["text"] == expected


@pytest.mark.parametrize(
    "node,expected",
    [
        ("collect_milk", "The drink keeper asks again: Milk or water?"),
        ("find_red_cup", "The cup keeper asks again: Red cup or blue cup?"),
        ("picnic_ready", "Ready or not yet? Let's hear: Our picnic is ready."),
    ],
)
def test_render_endpoint_reinvite_repeats_director_prompt_context(client, node, expected):
    response = client.post(
        "/interaction/render",
        json=_director_prompt_action(node=node, level=2, kind="reinvite"),
    )
    assert response.status_code == 200
    assert response.get_json()["text"] == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("action_id", "bad/action"),
        ("prompt_id", "unreviewed_s2"),
        ("feedback_id", "free_text"),
        ("node_id", "open_world"),
        ("phase", "invented"),
        ("world_role", "unreviewed role"),
        ("target_expression", "say anything"),
        ("language_level", True),
        ("scaffold_level", "2"),
        ("teaching_action", "improvise"),
        ("story_action", "rpg:free_text"),
        ("memory_policy", "write_now"),
    ],
)
def test_render_endpoint_rejects_unreviewed_enums_and_wrong_types(client, field, value):
    action = _rpg_action()
    action[field] = value
    response = client.post("/interaction/render", json=action)
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_action"}


def test_render_endpoint_rejects_unknown_fields_and_mismatched_references(client):
    unknown = _rpg_action()
    unknown["child_text"] = "speak this verbatim"
    assert client.post("/interaction/render", json=unknown).status_code == 400

    mismatched_story = _rpg_action()
    mismatched_story["story_action"] = "rpg:red_cup_ready"
    assert client.post("/interaction/render", json=mismatched_story).status_code == 400

    mismatched_prompt = _rpg_action()
    mismatched_prompt["prompt_id"] = "find_red_cup_s3"
    assert client.post("/interaction/render", json=mismatched_prompt).status_code == 400

    mismatched_prompt_content = _director_prompt_action()
    mismatched_prompt_content["feedback_id"] = "find_red_cup_s2"
    mismatched_prompt_content["story_action"] = "rpg:find_red_cup_s2"
    assert client.post("/interaction/render", json=mismatched_prompt_content).status_code == 400

    missing_required = _legacy_action()
    missing_required.pop("memory_policy")
    assert client.post("/interaction/render", json=missing_required).status_code == 400


def test_render_endpoint_accepts_terminal_rpg_condition(client):
    action = _rpg_action()
    action.update(
        {
            "prompt_id": "picnic_ready_s2",
            "feedback_id": "picnic_complete",
            "node_id": "picnic_ready",
            "phase": "completed",
            "world_role": "野餐向导",
            "target_expression": "Our picnic is ready.",
            "story_action": "rpg:picnic_complete",
            "success_condition": {"quest_completed": True},
        }
    )
    response = client.post("/interaction/render", json=action)
    assert response.status_code == 200
    assert response.get_json()["text"] == "Our picnic is ready. We did it!"
