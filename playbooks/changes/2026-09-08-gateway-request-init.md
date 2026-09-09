# Change: preserve strict RequestInit semantics for learning service calls

**Commit binding:** Same commit as this record.

## Summary

The Gateway learning-service helper now omits `RequestInit.body` on GET requests
instead of passing `undefined`. This satisfies consumers that enable TypeScript
`exactOptionalPropertyTypes` while preserving JSON POST request bodies.

## Layer

Backend Service.

## Contract impact

None. HTTP methods and JSON request payloads are unchanged.

## Files

- `backend/device_gateway/src/learning.ts`
- `backend/device_gateway/test/learning.test.ts`

## Verification

- `node --import tsx --test test/learning.test.ts` from `backend/device_gateway`: red before the implementation because GET included a `body` property; green after the implementation (2 passed).
- `npm test` from `backend/device_gateway`: 15 passed.
- `npm run typecheck` from `backend/device_gateway`: passed.
- `npm run build` from `backend/device_gateway`: passed.
- `npm test` from `clients/web`: 18 passed.
- `npm run typecheck` from `clients/web`: passed.
- `npm run build` from `clients/web`: passed.

## Rollback

Revert the two Gateway files and this record. No persistent state or external
contract data is affected.

## Reusable knowledge

No new skill: this is a narrow TypeScript optional-property compatibility fix,
covered by a stable unit regression test.
