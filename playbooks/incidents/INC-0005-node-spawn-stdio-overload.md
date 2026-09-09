# INC-0005 — Node spawn stdio overload changed the child-process type

## Fingerprint

`TS2322 ChildProcessByStdio<null, Readable, Readable> is not assignable to
ChildProcessWithoutNullStreams`, followed by `TS18048 child is possibly undefined`.

## Environment

- `backend/device_gateway`
- TypeScript NodeNext with `@types/node`
- Cross-process test launching Python through `node:child_process.spawn`

## Symptoms

The smoke behavior passed, but `npm run typecheck` failed because
`stdio: ["ignore", "pipe", "pipe"]` makes `stdin` statically `null`, while the
declared child type requires three non-null streams. Reusing an optional cleanup
variable also prevented narrowing.

## Root cause

Node's typed `spawn` overload derives the child-process stream types from the
stdio tuple. The test declared a stronger type than the selected overload
returns. A later optional assignment was not a stable non-null local binding.

## Attempts that did not work

Behavior tests alone did not reveal the problem because the JavaScript runtime
correctly launches a process with ignored stdin.

## Resolution

Use piped stdin so `spawn` returns `ChildProcessWithoutNullStreams`, immediately
call `processChild.stdin.end()`, and retain a non-optional local `processChild`
for test logic while keeping the optional outer variable only for cleanup.

## Verification

From `backend/device_gateway`, run `npm test` and
`npm run typecheck`; both must pass.

## Prevention

Keep stdio tuple types aligned with the declared child type. Prefer a local
non-null process binding and a separate optional cleanup reference.

## Skill decision

Do not promote yet. This is one TypeScript/Node interop incident; reuse this
incident first if the same compiler fingerprint recurs.
