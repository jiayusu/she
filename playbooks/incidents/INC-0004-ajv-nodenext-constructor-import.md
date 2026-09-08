# INC-0004 — Ajv 2020 default import is not constructable under NodeNext

## Signal

`npm test` passed, but `npm run typecheck` failed at `new Ajv2020(...)` with
`TS2351: This expression is not constructable`.

## Context

- Component: `backend/device_gateway`
- Compiler: TypeScript with `module` and `moduleResolution` set to `NodeNext`
- Dependency entry point: `ajv/dist/2020.js`

## Root cause

The Ajv CommonJS/ESM compatibility surface exposes both a default export and the
named `Ajv2020` class at runtime. Under this NodeNext configuration, TypeScript
resolved the default import as the module namespace rather than the declared
constructor, even though the test runner could execute it.

## Resolution

Import the explicitly declared named class:

```ts
import { Ajv2020 } from "ajv/dist/2020.js";
```

Do not suppress the error with `any`, `skipLibCheck`, or a constructor cast.

## Verification

Run from `backend/device_gateway`:

```powershell
npm test
npm run typecheck
```

Both commands must pass.

## Reuse rule

When a dual CommonJS/ESM dependency is executable but its default import is not
constructable under NodeNext, inspect its `.d.ts` and runtime export keys, then
prefer the explicit named class export when both agree.
