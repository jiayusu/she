# Change: define the embodied-language RPG product loop

**Commit binding:** Same commit as this record.

## Summary

Defined SHE's product loop as a finite, server-authoritative embodied-language RPG and froze the first
reviewed MVP story: request milk at the fridge, find the red cup at the table, then complete the picnic.
Documented the Agent triggers, Speech Act boundary, world-state transitions, trust boundaries, acceptance
criteria and staged implementation order before changing runtime behavior.

## Layer

Agent

## Contract impact

None in this documentation phase. The plan requires shared contracts to change before runtime consumers.

## Files

- `docs/architecture/12-embodied-language-rpg.md`
- `docs/plans/2026-09-08-embodied-language-rpg.md`
- `playbooks/decisions/ADR-0002-embodied-language-rpg.md`
- `AGENTS.md`
- `README.md`

## Verification

Documentation review commands were not run in the latest editing pass because the
user explicitly requested file edits without tests or verification. Links and
repository-path policy remain pending the next authorized repository audit.

## Rollback

Remove the new architecture document, plan, ADR and navigation entries. No runtime or persisted state changes
are introduced by this phase.

## Reusable knowledge

The state-machine and contract order are product-specific architecture. They remain an ADR and implementation
plan rather than a skill because no repeatable operational procedure has been demonstrated yet.
