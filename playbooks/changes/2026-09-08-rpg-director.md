# Change: implement the finite RPG decision path

**Commit binding:** Same commit as this record.

## Summary

Added a deterministic embodied-language RPG path to the Learning Director. Explicit RPG turns now load the
reviewed `milk_picnic.v1` seed, resolve a bounded Speech Act and required slots, keep quest success separate
from full-expression learning evidence, emit revisioned virtual world events, and select one child-facing
action for the next node. The legacy learning request shape remains available for migration callers.

## Layer

Agent.

## Contract impact

Backward-compatible TypeScript response extension. `DirectResponse.rpg` and reviewed content references on
`TeachingAction` are optional for legacy callers. Durable RPG requests add the fields already defined by the
shared `rpg-turn` contract; clients still cannot submit world state or mastery. The optional
`learning-event.assessment.pronunciation_intelligibility` field now also accepts `null` to represent the
absence of a dedicated evaluator; existing numeric values remain valid.

## Files

- `agents/director/src/types.ts`
- `agents/director/src/speech-act.ts`
- `agents/director/src/embodied-rpg.ts`
- `agents/director/src/learning-director.ts`
- `agents/director/src/assessment.ts`
- `agents/director/src/durable-learning.ts`
- `shared/contracts/v1/learning-event.schema.json`
- `docs/architecture/02-agents.md`
- `docs/architecture/08-contracts.md`
- `deploy/director.Dockerfile`

## Behavior

- A confirmed fridge observation presents the milk request task.
- A context-supported `Milk!` satisfies the quest criterion; `I want water.` resolves the wrong slot and does
  not change world state.
- Milk success grants only the virtual `milk_token` and moves to `find_red_cup`.
- Red-cup success grants `red_cup_token`, emits the finite completion event and ends the quest.
- Low ASR confidence does not increment failure state. Two clear failures or emotional distress pause output.
- World transitions require a prior reviewed RPG action; a legacy prompt cannot elicit a world mutation.
- Speech and resume events cannot skip a node's required-object gate; only a confirmed object context can
  enter the language-resolution branch.
- The selected language level is the nearest level declared by the reviewed seed, so malformed, fractional,
  or unsupported learner-state values cannot leak into the action.
- Assessment now requires all target-expression words for full-expression evidence, while Speech Act evidence
  independently controls quest progress.
- Assessment reports pronunciation intelligibility as `null` until a dedicated evaluator exists; ASR
  transcript confidence remains assessment confidence and no longer masquerades as pronunciation evidence.
- The Director container includes the reviewed `content/` tree so the runtime loader can resolve the seed in Compose.

## Verification

No test or type-check command was run after this implementation, per the user's explicit instruction to keep
editing without tests. The previously run baseline and story-seed/contract checks predate these runtime edits
and must not be treated as verification of this change.

## Rollback

Revert the listed Director files and this record together. Stored responses carrying `rpg` should no longer be
sent to a reverted Director unless the Shared State entries are migrated or cleared in a non-production demo.

## Reusable knowledge

The product invariant is encoded as deterministic code and shared contracts: an RPG transition must cite a
completed eliciting action and matching Speech Act slots. No new skill is warranted.
