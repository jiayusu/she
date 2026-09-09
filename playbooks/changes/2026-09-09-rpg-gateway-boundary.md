# Change: add the RPG Gateway contract boundary and safe quest projection

**Commit binding:** Same commit as this record.

## Layer

Backend Service / Shared Contract.

## Summary

Add the public boundary for the bounded `milk_picnic.v1` runtime:

- `POST /v1/rpg/direct` accepts only `rpg-turn.schema.json`, forwards the turn
  to the configured Learning Director, and rejects an upstream response whose
  `rpg` value does not match `rpg-decision.schema.json`;
- `GET /v1/rpg/state` validates identity-only query parameters, reads the
  Memory Store authority, and returns a `rpg-quest-summary` projection;
- the projection deliberately excludes the stored learning response, child
  utterance, Speech Act evidence, request hash, device/session metadata, and
  learning profile;
- delivery ACK is projected without mutating world state: persisted
  `presenting` becomes effective `awaiting_speech` after a completed ACK and
  `delivery_failed` after a failed or expired delivery.

The existing `/v1/learning/direct`, `/v1/learning/state`, and
`/v1/learning/execute` migration routes remain available.

## Contract impact

Backward-compatible v1 addition. `rpg-quest-summary.schema.json` is a new
read-only response schema; it does not add a client world-state write field.

## Files

- `shared/contracts/v1/rpg-quest-summary.schema.json`
- `shared/contracts/v1/fixtures/valid/rpg-quest-summary.json`
- `shared/contracts/v1/fixtures/invalid/rpg-quest-summary-raw-response.json`
- `shared/contracts/tests/test_contracts.py`
- `shared/contracts/validate_contracts.py`
- `shared/contracts/README.md`
- `backend/device_gateway/src/contracts.ts`
- `backend/device_gateway/src/app.ts`
- `backend/device_gateway/test/rpg-http.test.ts`
- `backend/device_gateway/README.md`
- `scripts/rpg-smoke.mjs`
- `playbooks/changes/2026-09-09-rpg-gateway-boundary.md`

## Verification

Not run, following the user's explicit instruction to edit files without
running tests, typechecks, builds, or verification commands. The new fixtures
and contract cases, Gateway route boundary cases, plus the synthetic full-quest
smoke were registered for the next authorized verification run.

## Rollback

Remove the two RPG routes, three validator members, quest-summary schema and
fixtures, and their catalog entries together. No data migration is needed;
the endpoint only projects existing Memory Store records.

## Reusable knowledge

A device-delivery phase and a world-state phase have different owners. Project
their effective combination at the Gateway, but never turn a TTS ACK into a
world event or let a client write either state.
