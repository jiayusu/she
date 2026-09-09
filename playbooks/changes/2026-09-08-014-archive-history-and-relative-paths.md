# Change: Archive superseded docs, remove duplicate data, finish relative-path conversion

**Commit binding:** Same commit as this record.

## Summary

Separated historical records from current truth, and converted the remaining 113 stale
absolute-path references to repo-relative paths (completing the rule change in
`playbooks/changes/2026-09-08-013-*`).

1. **Archived superseded docs** under `docs/archive/`, each with a banner marking it
   historical and non-authoritative:
   - `program.md` → `docs/archive/program-methodology.md`. A generic LLM build methodology
     that was never in use here: the `SPEC.md`/`BUILD.md`/`PLAN.md`/`DEVLOG.md` files it
     requires do not exist in this repository.
   - `docs/superpowers/` → `docs/archive/2026-09-07-vertical-slice/`. The 2026-09-07 plan and
     spec, already delivered. Its banner explicitly neutralizes the embedded
     "REQUIRED SUB-SKILL" line so no agent re-executes finished work, and records that its
     premise ("`engine`/`kg`/`store`/`po`/`route`/`zhihu` remain in place") is now false.
2. **Deleted two unreferenced duplicate data files.** `backend/knowledge_graph/data_seed.csv`
   and `data_word_variants.csv` were byte-identical to `data/seed.csv` and
   `data/word_variants.csv` (git hashes `85d9d36b` and `c7d0bb92`). All code reads the
   `data/` copies via `DATA = ROOT / "data"`; grep found no reference to the flat copies.
3. **Converted the remaining stale paths.** Live instructions now use repo-relative paths.
   Three cases needed judgement rather than substitution:
   - `INC-0001` and `2026-09-07-009-learning-director.md` referenced the retired `store/` and
     `route/` directories. Rewriting these to look runnable would have falsified the record,
     so they are labelled historical with today's equivalent noted alongside.
   - `INC-0002` quoted an external tool path from another machine's home directory; it is now
     a `<codex-home>` placeholder, since it never referred to this repository.
   - Relative paths are cwd-dependent where absolute ones were not. `README.md` and
     `backend/digital_twin/deployment.md` used `Set-Location`, which broke the *following*
     command block; both now use `Push-Location`/`Pop-Location` and state that paths are
     relative to the repository root.

## Layer

Repository.

## Contract impact

`none`. No schema, wire format, or runtime behavior changed.

## Files

- Moved: `docs/archive/program-methodology.md`, `docs/archive/2026-09-07-vertical-slice/**`.
- Deleted: `backend/knowledge_graph/data_seed.csv`, `backend/knowledge_graph/data_word_variants.csv`.
- Path conversion across 25 files: `README.md`, `clients/ios/README.md`,
  `backend/digital_twin/deployment.md`, `skills/she-ios-soft-orbit/SKILL.md`,
  `playbooks/{changes,incidents,releases}/*.md`.
- `scripts/audit_repository.ps1` — comment updated for the moved `program.md` path.
- `AGENTS.md` — §39 preamble reworded to describe absolute drive-letter paths in prose
  instead of showing a literal example, so the planned Phase 7 checker can stay strict
  without matching the rule that defines it (see Reusable knowledge).

## Verification

Working directory `.` (repository root) unless stated.

- `git grep -nE '[A-Za-z]:[\\]working' -- . ':!docs/archive'` → no matches (was 114).
  (The retired prefix is written as a regex, not a literal, so this record does not
  match its own search — see Reusable knowledge below.)
- `git grep -nE "[A-Za-z]:\\\\\\\\" -- '*.md' '*.ps1' '*.yml' '*.json' '*.ts' '*.py' '*.js' '*.swift' ':!docs/archive'`
  → only `scripts/release_readiness.ps1:25`, which is the detector regex itself.
- `audit_repository.ps1` → `370 tracked files checked; repository audit passed`, exit 0.
- `release_readiness.ps1` → exit 0.
- Component suites (run from each component directory, as `verify.ps1` does):
  `shared/contracts` 12 passed; `agents/interaction` 103 passed;
  `backend/memory_store` 61 passed; `backend/intel` 27 passed;
  `clients/hardware-rx5` 11 passed; `agents/director` 66 passed + typecheck clean;
  `backend/device_gateway` 10 passed + typecheck clean; RX5 simulator `--once` exit 0.

### Pre-existing failure, not introduced here

`backend/pointing` is 41/42. `tests/server.test.js:24` asserts the served homepage contains
`万物模式`, but `web/index.html` says `指向实验室` / `指向一个物件`. Both files are unmodified
since `init push` (`git diff origin/main...HEAD -- backend/pointing` is empty), and the
assertion already fails at `origin/main`. Tracked as a separate defect; not fixed here to keep
this commit documentation-only.

### Environment note

This checkout had no `node_modules` and no editable Python installs, so suites cannot run
until `npm ci` (device_gateway, director) and `pip install -e` (interaction, hardware-rx5)
are run. `backend/pointing` has **no tracked lockfile**, so `ci.yml:39`
(`npm ci --prefix .../backend/pointing`) cannot succeed as written. Tracked separately.

## Rollback

`git revert` this commit. The archived files return to their old paths and the duplicate CSVs
return. No state implications: the deleted files were unreferenced byte-identical copies, and
`data/seed.csv` and `data/word_variants.csv` are untouched.

## Reusable knowledge

Reinforces `INC-0006` (never scan a policy's explanatory text with the policy's own literal
rule): the path-conversion script rewrote a *description* of the bad path inside the previous
change record into a bare `.`, which had to be repaired by hand.

Scanning the repository with the naive pattern `[A-Za-z]:[\\]` produced four hits that are
**all legitimate**, and the Phase 7 checker must not reject them:

| Hit | Why it is not a stale path |
|---|---|
| `scripts/release_readiness.ps1:25` | The detector regex itself. |
| `agents/interaction/src/she_engine/schema.py:161` | `"discarded:\n"` — a string ending in a colon followed by an escape, not a drive letter. |
| `backend/intel/archive.py:26` | An illustrative comment (`如 D:\data`) explaining an out-of-tree data directory. |
| `docs/archive/**` | Historical records, deliberately preserved with banners. |

So the check needs a narrower pattern (drive letter + `:\` + a path-like segment, not any
`X:\`) plus exclusions for `scripts/` and `docs/archive/`. `AGENTS.md` §39's own wording was
changed in this commit from a literal example to prose for the same reason.

No new skill. The durable protection is that mechanical check, not a document (§39.5).
