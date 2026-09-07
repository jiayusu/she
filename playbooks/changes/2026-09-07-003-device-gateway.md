# Change: add deterministic Device Gateway

**Commit binding:** Same commit as this record.

## Summary

The parent control plane receives a typed demo HTTP API, while RDK devices receive a validated, ordered, idempotent WebSocket session boundary.

## Layer

Backend Service.

## Contract impact

Implements contract version `1.0` without changing it.

## Files

- `A:\working\she\backend\device_gateway\src`
- `A:\working\she\backend\device_gateway\test`
- `A:\working\she\backend\device_gateway\package.json`

## Verification

The initial test run failed with `ERR_MODULE_NOT_FOUND` for the intentionally absent Gateway modules. The finished suite must pass HTTP, schema, session, idempotency, ordering, and acknowledgement tests plus strict TypeScript checking.

## Rollback

Revert this commit. The service stores demo state in memory and has no persistent migration.

## Reusable knowledge

Unknown contract versions stay explicit errors; Gateway never weakens schema checks to hide producer/consumer skew.
