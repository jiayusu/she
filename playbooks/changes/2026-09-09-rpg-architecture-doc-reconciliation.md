# Change: reconcile Agent, Shared State, Web and iOS architecture docs

**Commit binding:** Same commit as this record.

## Layer

Repository / Agent / Shared State / Web / App.

## Summary

Reconciled four architecture documents with the current bounded RPG code and
separated implemented software surfaces from target product design:

- documented the seven Agent names as auditable responsibilities rather than
  seven independent LLM services;
- recorded the current `milk_picnic.v1` Director → Memory → Interaction →
  Gateway path, including `TeachingAction → text` rendering and durable Shared
  State ownership;
- replaced retired `engine`, `store` and `kb` ownership references with the
  canonical component paths;
- clarified that the RPG learning path persists structured evidence and does
  not store the child's verbatim utterance, while the legacy episodic API still
  has an `utterance` field and prevents a system-wide zero-raw-data claim;
- marked Web debug/quest UI, iOS quest UI, production Parent Agent summaries,
  authentication and real privacy export/erase as not implemented.

## Contract impact

None. The documents describe the existing `rpg-turn`, `rpg-decision` and
`rpg-quest-summary` contracts without changing their schemas.

## Files

- `docs/architecture/02-agents.md`
- `docs/architecture/03-shared-state.md`
- `docs/architecture/06-web.md`
- `docs/architecture/07-parent-app.md`
- `playbooks/changes/2026-09-09-rpg-architecture-doc-reconciliation.md`

## Verification

Not run, following the user's explicit instruction not to run tests, builds,
lint, typechecks, audits or verification commands. The documents were edited
from read-only inspection of the referenced source and component READMEs; link,
format and repository-policy checks remain pending an authorized verification
run.

## Rollback

Revert these five documentation files together. No runtime code, contract or
persisted data is changed.

## Reusable knowledge

A current architecture document should identify the owner and the maturity of
each surface independently. A backend endpoint, client button or in-memory
fallback is not evidence that the corresponding end-to-end product capability
is live.

