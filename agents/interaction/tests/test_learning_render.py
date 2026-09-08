from she_engine.learning_render import render


def test_learning_wording_respects_pause_and_known_targets():
    assert render({"target_expression": "I want milk.", "teaching_action": "pause", "scaffold_level": 6}) == "Let's listen together. You can join in when you like."
    assert "milk" in render({"target_expression": "I want milk.", "teaching_action": "ask", "scaffold_level": 2}).lower()
    assert render({"target_expression": "unreviewed", "teaching_action": "ask", "scaffold_level": 2}) == "Let's look around together."
