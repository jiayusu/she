# Change: persist and validate the bounded RPG world state

**Commit binding:** Same commit as this record.

## Layer

Shared State.

## Summary

Extend the existing learning-turn transaction so an optional `response.rpg`
decision is stored in the same response JSON as the teaching action. No client
world-state writer, table, or HTTP endpoint is added. The next turn restores its
authority only from `latest.response.rpg`; once a session starts the RPG, a later
turn cannot omit that state and restart the story.

The validator intentionally supports only reviewed `milk_picnic` version 1:

- the first state is `collect_milk` at world revision 1 with empty inventory and
  no completed nodes;
- `collect_milk -> find_red_cup` advances 1 to 2, grants only `milk_token`, and
  completes only `collect_milk`; its committed phase must be `seeking_object`;
- `find_red_cup -> picnic_ready` grants `red_cup_token` at 2 to 3, then completes
  the quest at 3 to 4 in the same transaction with the terminal node marked done
  and phase fixed to `completed`;
- transition evidence must satisfy the current criterion, belong to the current
  turn, cite the exact previously persisted `action_id` and scaffold level,
  carry confidence of at least 0.8, and be the evidence referenced by every event;
- a world transition additionally requires the previous delivery to be
  `completed`, the previous phase to be `presenting/awaiting_speech`, a valid
  `confirmed_object`, and the exact reviewed S0-S6 prompt ID matching the node
  and persisted scaffold level;
- no-event turns keep the current node, revision, inventory, and completed-node
  set unchanged.
- `confirmed_object` must belong to the current node, is required for presentation/evaluation phases,
  and must be cleared while seeking the next node or after completion.
- Every stored RPG TeachingAction must point back to the same node, phase, role and finite content ID;
  prompt IDs must match its scaffold suffix, while success/help feedback is restricted to its reviewed
  action kind. This prevents a structurally valid world state from carrying contradictory child output.

The existing `(session_id, turn_id)` replay and request-hash conflict handling
runs before transition validation, so a same-turn retry returns the already
committed response and cannot grant the same token twice.

The reviewed target-expression allowlist now also contains the red-cup selection
and terminal picnic expressions emitted by those two story nodes.

## Contract impact

Backward-compatible optional response field. Existing non-RPG learning turns
continue unchanged. RPG values follow `shared/contracts/v1/rpg-decision.schema.json`,
with the additional server-side cross-field and previous-state checks that JSON
Schema cannot express.

## Files

- `backend/memory_store/memstore/learning.py`
- `backend/memory_store/tests/test_learning_rpg.py`
- `playbooks/changes/2026-09-08-rpg-memory-state.md`

## Erase behavior

RPG state remains inside `learning_turns.response`. `learning_turns.session_id`
already references `sessions.session_id ON DELETE CASCADE`, so the existing
child/session erase path removes the RPG turn and its events without a separate
deletion implementation. The added regression case covers that ownership path.

## Verification

Tests were added but **not run**, per the user's explicit instruction not to run
tests or verification commands in this change.

## Rollback

Revert the validator, its call from `LearningStore.commit`, the RPG regression
test module, and this record together. No schema migration or persisted-data
rewrite is required because RPG state uses the existing response JSON column.

## Reusable knowledge

Finite story state needs transaction-time checks in addition to JSON Schema:
dynamic revision continuity, prior-node ownership, canonical inventory, and
event-to-evidence linkage all depend on the last committed server response. The
same boundary must also receive the previous delivery record and TeachingAction;
schema-valid evidence alone is not proof that a child heard the prompt.
