# Change: Require repo-relative paths and make the component table match disk

**Commit binding:** Same commit as this record.

## Summary

Removed the root cause of 271 stale absolute-path references — a hard-coded Windows
checkout directory that no longer exists — and the AGENTS.md self-contradiction about
which backend components exist.

Two defects were fixed at their source:

1. §39 mandated **absolute** paths for all Coding Agent work. That rule is what produced
   271 unusable references across 27 files: the repository is checked out at a different
   path than the one the rule hard-coded, and CI runs on Linux. §39 now mandates
   repo-relative paths and states why.
2. §29 listed the retired directories `engine`, `kb`, and `store` as
   "当前后台组件" (current backend components) while line 8 of the same file called them
   retired. None of the three exist on disk. §29 is now the real component table and maps
   each retired directory to the component that replaced it.

Also recorded that `backend/digital_twin/` holds documentation only — the implementation
is `backend/device_gateway/src/digital-twin.ts`. An agent looking for twin code in the
directory named after it would previously have found nothing.

## Layer

Repository.

## Contract impact

`none`. No schema, wire format, or runtime behavior changed.

## Files

- `AGENTS.md` — §39 path rule and preamble, §39.1/§39.3/§39.4/§39.5 path references, §29 component table.

No test files: the enforcing check is mechanical and lands in
`scripts/audit_repository.ps1` in a later commit of this reorganization.

## Verification

Working directory `.` (repository root):

- `git grep -cE '[A-Za-z]:\\\\' -- AGENTS.md` → no matches (was 7 stale absolute paths).
- `pwsh -NoProfile -Command "& './scripts/audit_repository.ps1'"` →
  `[audit] 371 tracked files checked; repository audit passed`, exit 0.
- `pwsh -NoProfile -Command "& './scripts/release_readiness.ps1'"` →
  `[release] canonical paths, legacy references, and tracked secret paths checked`, exit 0.

`scripts/verify.ps1` was not required for this commit: no code, test, or dependency
changed. It runs at the phases of this reorganization that touch ports and packaging.

## Rollback

`git revert` this commit. Documentation-only, no state implications. Reverting restores
the absolute-path rule, which would reintroduce the non-portable references.

## Reusable knowledge

No incident or skill. This was a stale-rule defect found by auditing the repository
against disk, not a reproducible failure. The durable protection is the planned
`audit_repository.ps1` check rejecting absolute drive-letter paths in tracked files;
a documentation skill would be weaker than that mechanical gate (§39.5).
