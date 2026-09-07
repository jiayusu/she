# Change: make store temporal tests deterministic

**Commit binding:** Same commit as this record.

## Summary

Relative-time recall tests no longer depend on the calendar date when the suite runs.

## Layer

Shared State.

## Contract impact

Backward-compatible. `MemoryService.recall()` adds an optional `now` parameter; existing callers behave unchanged.

## Files

- `A:\working\she\store\memstore\service.py`
- `A:\working\she\store\tests\test_timeline.py`
- `A:\working\she\playbooks\incidents\INC-0001-store-temporal-wall-clock.md`

## Verification

- Focused regression: 1 passed.
- Full store suite: 61 passed.

## Rollback

Revert this logical change. No persisted state or schema migration is involved.

## Reusable knowledge

See `A:\working\she\playbooks\incidents\INC-0001-store-temporal-wall-clock.md`.
