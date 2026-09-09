# Change: Render finite Embodied Language RPG actions through Xiao P

**Commit binding:** Same commit as this record.

## Summary

Interaction now turns a Director-owned TeachingAction into distinct reviewed copy
for `ask`, `prompt`, `reinvite`, `advance_story`, `pause` and `explore` instead of
collapsing most actions into one scaffold prompt. The renderer covers the approved
`milk_picnic` sequence `collect_milk -> find_red_cup -> picnic_ready`, including
the reviewed transition feedback:

- `milk_ready`: `Milk is ready. Find a cup!`
- `red_cup_ready`: `Red cup! Our picnic is ready!`
- `picnic_complete`: `Our picnic is ready. We did it!`

The object role remains story context relayed by Xiao P; it does not create another
child-facing personality. The changes do not control a fridge, cup or any other
physical object.

## Layer

Agent presentation and its internal HTTP boundary. Director decisions, Shared State,
Assessment, device transport and safety-filter policy are unchanged.

## Contract impact

Backward-compatible extension of the internal `POST /interaction/render` request.
Existing TeachingAction fields remain accepted. The endpoint additionally accepts
the optional RPG fields `action_id`, `prompt_id`, `feedback_id`, `node_id`, `phase`
and `world_role`.

The boundary rejects unknown top-level fields, wrong primitive types, invalid action
IDs, unreviewed targets/actions/story actions, and values outside the finite
`milk_picnic` node, prompt, feedback, phase and role sets. It accepts three finite
`success_condition` shapes: the legacy target check, either approved nonterminal
Speech Act criterion, or the terminal `quest_completed` marker. An RPG
`story_action` must equal the reviewed `rpg:<feedback_id>` reference. A prompt ID,
when supplied, must carry the same S0-S6 level as `scaffold_level`.

The success feedback may refer to the node just completed while `node_id`, role,
target and prompt describe the next node. The renderer therefore does not incorrectly
require feedback and next-node context to belong to the same node.

## Safety and invariants

- Caller strings are never interpolated into child-facing output.
- `target_expression`, `story_action`/`feedback_id`, `world_role`, node and prompt
  values only select complete reviewed rows from enum tables.
- Contradictory or unknown context used through the Python library returns the fixed
  reviewed fallback.
- Every selected string and the fallback pass through the existing
  `LocalSafetyFilter`; this change does not modify or bypass filter rules.
- Interaction only renders the Director's one chosen action. It does not judge a
  Speech Act, advance world state, write memory or infer mastery.

## Files

- `agents/interaction/src/she_engine/learning_render.py`
- `agents/interaction/server.py`
- `agents/interaction/tests/test_learning_render.py`
- `agents/interaction/tests/test_learning_server.py`
- `agents/interaction/pyproject.toml`
- `agents/interaction/README.md`
- `playbooks/changes/2026-09-08-rpg-interaction.md`

## Verification

Tests and validation commands were deliberately **not run**, as explicitly requested
by the user. Regression coverage was authored for action-specific wording, all three
story nodes, cross-node success feedback, final safety filtering, legacy TeachingAction
compatibility, strict HTTP enums/types and malformed-reference rejection, but there is
no execution evidence for this change yet.

Suggested later commands, when testing is authorized, from `agents/interaction`:

```sh
python -m pytest tests/test_learning_render.py tests/test_learning_server.py -q
python -m pytest tests -q
```

## Rollback

Revert the files listed above together. No state migration, content download, database
write or device-side rollback is required.

## Reusable knowledge

This is product-specific finite content and boundary validation, not a reusable
multi-project procedure, so no new skill is warranted. Future story seeds must add
reviewed enum rows and tests before their identifiers are accepted by Interaction.
