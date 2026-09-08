"""Reviewed finite learning prompts; Interaction remains the only child-facing voice."""
from .safety import LocalSafetyFilter

PROMPTS = {
    "I want milk.": ("Milk or water?", "I want...", "I want milk."),
    "I want water.": ("Water or milk?", "I want...", "I want water."),
    "I like apples.": ("Apples or bananas?", "I like...", "I like apples."),
    "Open, please.": ("Open or close?", "Open...", "Open, please."),
}


def render(action):
    target = action.get("target_expression")
    level = action.get("scaffold_level", 6)
    kind = action.get("teaching_action")
    if kind == "pause" or level == 6:
        text = "Let's listen together. You can join in when you like."
    elif target not in PROMPTS:
        text = "Let's look around together."
    elif kind == "reinvite":
        text = "I'm listening. Would you like to try again?"
    else:
        choice, starter, model = PROMPTS[target]
        text = choice if level <= 2 else starter if level == 3 else model
    ok, filtered = LocalSafetyFilter().filter(text, context="invite")
    return filtered if ok else "Let's look around together."
