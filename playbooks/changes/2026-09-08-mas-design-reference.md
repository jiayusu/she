# Change: MAS lifecycle design reference

**Commit binding:** Same commit as this record.

## Summary

Write a Chinese Markdown proposal using fetched primary Claude Code, Codex and
Hermes documentation as references. Include current SHE code boundaries, pain points,
comparison, proposed lifecycle/gates, typed draft, budgets, cancellation/idempotency,
fault-injection acceptance matrix and staged iteration.

## Layer

Repository documentation only. Reference document plus a linked first-stage implementation record.

## Contract impact

None. Draft interfaces remain in Markdown; any future implementation must first
update shared contracts and add failing tests.

## Files

`docs/architecture/11-agentic-loop-design-reference.md`.

## Verification

Opened the official sources linked inline and inspected current Director, hooks,
audit and architecture files. Confirmed proposal terminology is marked as draft,
reference products are not dependencies, and distinguishes the implemented first stage from deferred production mechanisms.

## Rollback

Remove the document and its README link. No runtime or state change.

## Reusable knowledge

Keep as a design reference. No new operational skill.
