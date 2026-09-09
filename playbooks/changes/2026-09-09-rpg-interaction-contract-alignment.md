# Change: align Interaction with Director RPG prompt content

**Commit binding:** Same commit as this record.

## Summary

The Director uses one reviewed prompt identifier as `prompt_id`, `feedback_id` and
`story_action=rpg:<id>` when it presents or re-invites an RPG prompt. Interaction
previously accepted those identifiers only in `prompt_id`; its HTTP boundary rejected
the otherwise valid Director action before rendering.

Interaction now defines the finite RPG content set as the union of the existing
result-feedback IDs and reviewed S0-S6 prompt IDs. Both the HTTP boundary and the
defensive library renderer accept only that union. A prompt content ID must still
equal `prompt_id`, carry the same scaffold level, use an ask/prompt/reinvite action,
and match the `rpg:<id>` story-action reference.

RPG `reinvite` copy is now scaffold-specific. It repeats the relevant choice,
sentence starter or full model instead of asking a context-free generic question.
In particular, the S2 milk and cup re-invites repeat `Milk or water?` and
`Red cup or blue cup?`, so a later bounded short form has a real eliciting context.

## Layer

Agent presentation and its internal HTTP boundary only. Director decisions, Shared
State, device delivery and safety-filter policy are unchanged.

## Contract impact

This aligns the existing internal `POST /interaction/render` boundary with the
Director's already-emitted action shape. It does not add an open string field or a new
shared cross-service schema. Existing result-feedback IDs and legacy TeachingAction
requests remain accepted.

## Safety and invariants

- No caller-provided string is interpolated into child-facing output.
- Prompt and result content remain complete rows in finite reviewed tables.
- Prompt content IDs must agree across `prompt_id`, `feedback_id`, scaffold level and
  `story_action`; contradictory node/role/target context falls back or is rejected.
- Cross-node success feedback remains valid: a completed-node feedback ID may still
  accompany the next node's prompt context.
- Selected text and fallback text continue through the unchanged final
  `LocalSafetyFilter`.

## Files

- `agents/interaction/src/she_engine/learning_render.py`
- `agents/interaction/server.py`
- `agents/interaction/tests/test_learning_render.py`
- `agents/interaction/tests/test_learning_server.py`
- `agents/interaction/README.md`
- `playbooks/changes/2026-09-09-rpg-interaction-contract-alignment.md`

## Verification

Regression test source was added for Director-style prompt IDs at S1-S3 across all
three MVP nodes, prompt-reference mismatches and scaffold-specific S2 re-invites.
Tests, builds, lint, type checking and audit commands were deliberately **not run**,
as explicitly requested by the user. This change therefore has static review only,
not runtime verification evidence.

Suggested later commands, only when testing is authorized, from
`agents/interaction`:

```sh
python -m pytest tests/test_learning_render.py tests/test_learning_server.py -q
python -m pytest tests -q
```

## Rollback

Revert the files listed above together. No state or device rollback is required.

## Reusable knowledge

When an action references reviewed content, the producer and renderer must share the
same finite identifier semantics. Re-invitation is not merely social copy: if a speech
resolver permits prompt-dependent short forms, the rendered re-invite must actually
re-establish that prompt context.
