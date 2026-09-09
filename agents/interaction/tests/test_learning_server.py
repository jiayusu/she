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


def test_render_endpoint_accepts_legacy_and_rpg_teaching_actions(client):
    legacy = client.post("/interaction/render", json=_legacy_action())
    assert legacy.status_code == 200
    assert legacy.get_json()["text"] == "Milk or water?"

    rpg = client.post("/interaction/render", json=_rpg_action())
    assert rpg.status_code == 200
    assert rpg.get_json()["text"] == "Milk is ready. Find a cup!"


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
