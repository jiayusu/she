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
- `agents/director/test/embodied-rpg.test.ts`
- `agents/director/test/durable-learning.test.ts`
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
- Durable turns restored from Shared State are marked persistent and are not discarded by the Director's
  15-minute in-memory cache TTL.
- A new RPG turn is rejected while the previous action is planned/issuing; failed or expired delivery can
  only enter the explicit `resume` recovery path.
- If a committed transition's success feedback failed delivery, resume emits the same reviewed feedback with
  no world events; repeated recovery failures remain recoverable, and the reward/revision is neither rolled
  back nor duplicated.
- Speech and resume events cannot skip a node's required-object gate; only a confirmed object context can
  enter the language-resolution branch.
- Speech turns require `detected_object=null`, preventing stale perception from being smuggled into the
  language event.
- The accepted object is persisted as `confirmed_object` on the bounded RPG decision and cleared on every
  node transition, so `phase=presenting` cannot by itself fabricate embodied context.
- The selected language level is the nearest level declared by the reviewed seed, so malformed, fractional,
  or unsupported learner-state values cannot leak into the action.
- Completed quest steps provide bounded recent-success history: each prior success withdraws one scaffold
  level (up to two), while clear failures add support and two failures still pause.
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
