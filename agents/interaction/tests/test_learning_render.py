import she_engine.learning_render as learning_render
from she_engine.learning_render import SAFE_FALLBACK, render


def test_learning_wording_respects_pause_and_known_targets():
    assert render({"target_expression": "I want milk.", "teaching_action": "pause", "scaffold_level": 6}) == "Let's listen together. You can join in when you like."
    assert "milk" in render({"target_expression": "I want milk.", "teaching_action": "ask", "scaffold_level": 2}).lower()
    assert render({"target_expression": "unreviewed", "teaching_action": "ask", "scaffold_level": 2}) == SAFE_FALLBACK


def _rpg_action(kind="ask", *, node="collect_milk", level=2, feedback="milk_help"):
    contexts = {
        "collect_milk": ("I want milk.", "饮品保管员"),
        "find_red_cup": ("I choose the red cup.", "杯子管理员"),
        "picnic_ready": ("Our picnic is ready.", "野餐向导"),
    }
    target, role = contexts[node]
    return {
        "action_id": "action-001",
        "prompt_id": f"{node}_s{level}",
        "feedback_id": feedback,
        "node_id": node,
        "phase": "presenting",
        "world_role": role,
        "target_expression": target,
        "scaffold_level": level,
        "teaching_action": kind,
        "story_action": f"rpg:{feedback}",
    }


def test_rpg_actions_have_distinct_reviewed_copy():
    rendered = {
        kind: render(
            _rpg_action(
                kind,
                feedback="milk_ready" if kind == "advance_story" else "milk_help",
            )
        )
        for kind in ("ask", "prompt", "reinvite", "advance_story", "pause", "explore")
    }

    assert len(set(rendered.values())) == len(rendered)
    assert rendered["ask"] == "The drink keeper asks: Milk or water?"
    assert rendered["prompt"] == "Milk or water? Let's choose."
    assert rendered["advance_story"] == "Milk is ready. Find a cup!"


def test_rpg_scaffolds_and_all_three_nodes_use_reviewed_rows():
    assert render(_rpg_action(level=3)) == "The drink keeper is listening: I want..."
    assert render(
        _rpg_action(node="find_red_cup", feedback="red_cup_help")
    ) == "The cup keeper asks: Red cup or blue cup?"
    assert render(
        _rpg_action(node="picnic_ready", feedback="picnic_pause")
    ) == "The picnic guide says our pretend picnic is ready."
    assert render(
        _rpg_action(node="find_red_cup", kind="advance_story", feedback="milk_ready")
    ) == "Milk is ready. Find a cup!"
    assert render(
        _rpg_action(node="picnic_ready", kind="advance_story", feedback="red_cup_ready")
    ) == "Red cup! Our picnic is ready!"
    assert render(
        _rpg_action(node="picnic_ready", kind="advance_story", feedback="picnic_complete")
    ) == "Our picnic is ready. We did it!"


def test_unknown_or_contradictory_dynamic_values_are_never_interpolated():
    unknown_role = _rpg_action()
    unknown_role["world_role"] = "<script>unknown keeper</script>"
    assert render(unknown_role) == SAFE_FALLBACK

    contradictory = _rpg_action()
    contradictory["world_role"] = "杯子管理员"
    assert render(contradictory) == SAFE_FALLBACK

    unknown_feedback = _rpg_action()
    unknown_feedback["feedback_id"] = "child supplied feedback"
    unknown_feedback["story_action"] = "rpg:child supplied feedback"
    assert render(unknown_feedback) == SAFE_FALLBACK

    malformed_action = _rpg_action()
    malformed_action["teaching_action"] = []
    assert render(malformed_action) == SAFE_FALLBACK


def test_rendered_and_fallback_text_both_pass_final_safety(monkeypatch):
    calls = []

    class RejectFirstText:
        def filter(self, text, context=""):
            calls.append((text, context))
            return (True, text) if text == SAFE_FALLBACK else (False, "")

    monkeypatch.setattr(learning_render, "LocalSafetyFilter", RejectFirstText)

    assert render(_rpg_action()) == SAFE_FALLBACK
    assert calls == [
        ("The drink keeper asks: Milk or water?", "invite"),
        (SAFE_FALLBACK, "invite"),
    ]
