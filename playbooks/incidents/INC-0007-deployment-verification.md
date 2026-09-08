# Incident: Windows test discovery and unverified web build

## Fingerprint

`npm test --prefix backend/device_gateway` failed with `Could not find ... test/*.test.ts`
on Windows Node 20. The newly included web build reported TS2307 aliases, TS2375
optional fields, and an unsupported Vite extensionAlias option. Web tests resolved
fixtures under clients/shared and imported the Gateway under clients/backend.

## Environment

Windows, Node 20.15.1, npm; repository verification and parent web.

## Symptoms

Gateway tests did not execute. Parent web could not build; four fixture tests failed
and the live Gateway suite could not load. Pointing assertions used retired page
labels and assumed a global WebSocket unavailable in Node 20.

## Root cause

Test commands depended on shell glob expansion. Web was absent from CI, allowing
repository-relative paths, bundler configuration and strict optional typing to drift.
Pointing test page names had not followed the existing UI rename.

## Attempts that did not work

Node 20.15.1 rejected the experimental-global-websocket flag. Replaced that assumption
with an explicit ws development dependency. Removed an extra config brace introduced
during editing before rerunning validation.

## Resolution

Enumerate test files with a shared Node runner. Configure TypeScript aliases, use
supported Vite configuration, correct repository test paths and omit absent optional
patch properties. Include web tests, typecheck and build in verification and CI.
Update pointing assertions to the actual page titles and import its WebSocket client.

## Verification

Gateway: 12 tests passed. Web: 15 tests passed; typecheck and production build passed.
Director: 66 tests passed. Compiled Gateway dashboard and local deployment smoke passed.
Commands: `npm test --prefix backend/device_gateway`, `npm test --prefix clients/web`,
`npm run typecheck --prefix clients/web`, `npm run build --prefix clients/web`,
`node scripts/deployment-smoke.mjs`.

## Prevention

CI now builds and tests the parent web and runs the Compose deployment smoke check.

## Skill decision

Keep as incident: mechanical test/build checks are more appropriate than a new skill.

The final iOS source check also falsely rejected the present quoted 17.0 target:
PowerShell native argument passing removed regex quotes. Using Select-String keeps
the exact pattern in PowerShell, consistent with the native quoting issue already
documented in `scripts/audit_repository.ps1`. No iOS source changed.
