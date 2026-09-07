# INC-0006 — Source audit matched its own documentation

## Fingerprint

The `iOS source contract` verification stopped after printing the forbidden
regex from `clients/ios/README.md`, even though application source contained no
heavyweight 3D import or unscoped animation.

## Environment

- `A:\working\she\scripts\verify.ps1`
- Windows PowerShell 7
- Ripgrep audit covering the entire `A:\working\she\clients\ios` tree

## Symptoms

All component suites passed, then the final source audit failed because the
README documents the exact `SceneKit|RealityKit|...` command users should run.

## Root cause

The forbidden-code search scope included documentation. Documentation naturally
contains the forbidden tokens while explaining the policy, so the audit matched
itself instead of application code.

## Attempts that did not work

Searching the whole iOS directory appeared simpler but mixed executable source,
configuration, tests, and instructional prose into one policy domain.

## Resolution

Restrict forbidden source patterns to
`A:\working\she\clients\ios\SHEParentApp`. Check the deployment target directly
in `A:\working\she\clients\ios\project.yml`. Use thrown errors with explicit
messages for missing required patterns or present forbidden patterns.

## Verification

Run `A:\working\she\scripts\verify.ps1` from any working directory. The iOS
source contract must pass while the script still fails if a forbidden import is
placed in application source.

## Prevention

Partition source, configuration, test, and documentation audits. Never scan a
policy's explanatory text with the same literal rule without exclusions.

## Skill decision

Do not promote yet. Reuse this incident if another static audit self-matches;
promote only after the pattern proves reusable across multiple audit domains.

## Same-task recurrence

The repository path audit also classified the tracked, deliberately sanitized
`zhihu/.env.example` as a secret because the `.env` regex did not distinguish an
example template. The same prevention rule applied: partition true secrets from
safe explanatory artifacts. The path regex now permits exactly `.env.example`
while continuing to reject `.env` and other `.env.*` variants. This second case
occurred in the same delivery change, so it is retained as incident knowledge
rather than promoted prematurely to a skill.
