# Change: define versioned cross-platform contracts

**Commit binding:** Same commit as this record.

## Summary

Gateway, RDK runtime, and iOS receive one v1 contract source with canonical valid and invalid fixtures.

## Layer

Repository and Backend Service boundary.

## Contract impact

Introduces contract version `1.0`.

## Files

- `A:\working\she\shared\contracts\v1`
- `A:\working\she\shared\contracts\tests\test_contracts.py`
- `A:\working\she\shared\contracts\validate_contracts.py`

## Verification

- The initial suite failed because the expected schemas were absent.
- The finished pytest suite passed 12 tests.
- The standalone validator accepted six valid fixtures and rejected five invalid fixtures.
- A malformed compressed conditional schema was resolved and documented in `A:\working\she\playbooks\incidents\INC-0003-json-schema-brace-compression.md`.

## Rollback

Revert this commit before any v1 client is released. Once a client ships, replace v1 only through a versioned migration.

## Reusable knowledge

Contract order is enforced by fixtures and validators rather than a redundant documentation skill.
