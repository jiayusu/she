# Change: Split AGENTS.md into a hub plus topic files

**Commit binding:** Same commit as this record.

## Summary

`AGENTS.md` was 2634 lines / 52 KB, so any agent needing one rule had to load the entire
architecture spec. It is now a 225-line hub — ownership map, hard rules (§20, §28, §29, §38,
§39), and a navigation table — with the architecture detail split by topic under
`docs/architecture/`.

Two further problems are fixed by the split itself:

- **Aspirational content is now labelled.** §24 and §37 describe a target directory layout that
  does not exist on disk (`learner_model/`, `curriculum/`, `backend/engine/`, `clients/web/`, …).
  They now live in `docs/architecture/99-target-state.md`, whose title and first line say
  ASPIRATIONAL. Previously an agent reading §24 could mistake it for the real tree.
- **Completed migration history is archived.** §22 and §23 describe migrating away from the
  retired five-minister directories. They move to `docs/archive/migration-legacy-ministers.md`
  with a banner stating the migration is done and that §28 forbids restoring that architecture.

**Section numbers are deliberately preserved** (§0–§39, not renumbered) so existing
cross-references such as "AGENTS.md §22/§28" keep resolving.

## Layer

Repository.

## Contract impact

`none`. Documentation only; no schema, wire format, or runtime behavior changed.

## Files

- `AGENTS.md` — reduced to hub: preamble, Canonical Ownership Map, navigation table, component
  doc convention, and §20/§28/§29/§38/§39 verbatim.
- `docs/architecture/{01-overview,02-agents,03-shared-state,04-backend-services,05-hardware-rx5,06-web,07-parent-app,08-contracts,09-runtime-flows,10-testing,99-target-state}.md` — new.
- `docs/archive/migration-legacy-ministers.md` — new (§22, §23).
- `README.md` — added a 文档入口 section, and corrected the `backend/digital_twin` description,
  which still claimed that directory holds the authoritative twin.

One line of the ownership map was intentionally rewritten:
`backend/digital_twin  server-owned device twin state` →
`documentation only; twin implementation lives in backend/device_gateway/src/digital-twin.ts`.
That directory contains only two `.md` files; the implementation is
`backend/device_gateway/src/digital-twin.ts`.

## Verification

The split was done by line-range extraction, not by hand, with two mechanical gates.

1. **Ownership check, before writing anything.** Every one of the 2635 source lines is claimed
   by exactly one output file; the script aborts on a double-claim or an unclaimed line.
   Result: `conservation OK: all 2635 lines claimed exactly once`
   (hub 189, architecture 2341, archive 105).
2. **Content-conservation check, after writing.** Multiset comparison of every non-blank,
   non-`---` line in `git show HEAD:AGENTS.md` against the union of the 13 output files:
   `PASS: every original content line is present in the new files`
   — 1942 original content lines, +76 added (file headers, nav table, banners). The only
   reported difference was the intentional `digital_twin` rewrite above, confirmed by hand.
   (Re-running this check requires the pre-split blob: `git show 1d44ba2:AGENTS.md`.)
3. All 12 navigation links resolve — each target checked with `test -e`.
4. `wc -l AGENTS.md` → 225 (was 2634).
5. `audit_repository.ps1` → `348 tracked files checked; repository audit passed`, exit 0.
6. `release_readiness.ps1` → exit 0. Its legacy-reference scan covers code extensions only
   (`.py|.ts|.js|.swift|.ps1|.yml|.json`), not `.md`, so the archived migration text naming
   `engine`/`store` does not trip it.

Not run: `verify.ps1` component suites. No code, test, or dependency changed.

## Rollback

`git revert` this commit. `AGENTS.md` returns to its 2634-line form and the new files disappear.
No state implications.

## Reusable knowledge

Not a skill, but the reusable technique for splitting a large authored file:

**Verify conservation mechanically, in two stages — claim before write, diff after write.** The
claim stage catches a range typo (a line assigned to two files, or to none) *before* any file is
created, so a mistake never reaches disk. The diff stage catches silent loss from editing while
moving. A line-count total is not sufficient: it cannot distinguish a dropped line from an added
header. Comparing line *multisets* can, and it also flags any line that was quietly reworded —
which is how the one intentional `digital_twin` edit surfaced and got recorded rather than
slipping through unnoticed.
