# Change: define bounded embodied-language RPG contracts

**Commit binding:** Same commit as this record.

## Summary

Adds `rpg-turn` and `rpg-decision` JSON Schemas to the v1 shared-contract
catalogue. Device/client input is limited to identity, a perception reference,
and bounded observation fields. Director RPG output is limited to finite phases,
speech acts, slots, revision-bearing world events, and asset references; it
does not allow world-state or mastery writes, arbitrary state patches, or raw
child data.

The later contract tightening requires `detected_object=null` on speech turns,
adds server-derived `confirmed_object` to RPG decisions and child-safe quest
summaries, and makes the `milk_picnic.v1` node state, role, content, item,
criterion and event identifiers finite at the Gateway boundary. Adding another
seed requires an explicit reviewed contract update instead of arbitrary IDs.

## Layer

Shared State.

## Contract impact

Backward-compatible. New standalone v1 schemas do not modify
`device-event.schema.json` or `device-command.schema.json`.

## Files

- `shared/contracts/v1/rpg-turn.schema.json`
- `shared/contracts/v1/rpg-decision.schema.json`
- `shared/contracts/v1/rpg-quest-summary.schema.json`
- `shared/contracts/v1/fixtures/valid/rpg-turn.json`
- `shared/contracts/v1/fixtures/valid/rpg-turn-speech.json`
- `shared/contracts/v1/fixtures/valid/rpg-decision.json`
- `shared/contracts/v1/fixtures/invalid/rpg-turn-world-state.json`
- `shared/contracts/v1/fixtures/invalid/rpg-turn-speech-stale-object.json`
- `shared/contracts/v1/fixtures/invalid/rpg-decision-state-patch.json`
- `shared/contracts/v1/fixtures/invalid/rpg-decision-unknown-world-event.json`
- `shared/contracts/v1/fixtures/invalid/rpg-decision-unreviewed-content.json`
- `shared/contracts/tests/test_contracts.py`
- `shared/contracts/validate_contracts.py`
- `shared/contracts/README.md`

## Verification

- `python -m pytest tests -q` from `shared/contracts`: red before the schemas
  existed (five expected missing-schema failures); green after implementation
  (23 passed).
- `python validate_contracts.py` from `shared/contracts`: 11 valid accepted and
  11 invalid rejected.

Those commands describe the initial schema addition only. No contract command
was run after the speech/confirmed-object/summary tightening, per the user's
explicit no-test instruction; the current aggregate remains unverified.

## Rollback

Revert the schema, fixture, validator-list, test-list, README, and this record
together. They have no runtime consumer in this change and do not mutate
persisted state.

## Reusable knowledge

No new skill: JSON Schema cannot generally assert that one dynamic numeric
field equals another plus one. The schemas require bounded `base_revision` and
`resulting_revision`; a later Shared State transaction test must enforce their
monotonic relationship atomically.
