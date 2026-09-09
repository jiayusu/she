# Change: Untrack ~60 MB of KG build artifacts and close the ignore gap

**Commit binding:** Same commit as this record.

## Summary

Removed 24 generated binary files (~60 MB) from Git tracking and fixed the `.gitignore` bug
that let them in. Tracked repository content drops from ~64 MB to ~2.7 MB (371 → 347 files).

Root cause: both ignore files listed these artifacts by **path**, anchored at `data/`
(`data/embeddings/`, `data/snapshots/`, `data/kg.graphml`, …). The files were committed under
`backend/knowledge_graph/kg/data/` — a different directory — so every rule missed them. The
component's own ignore file already declared this exact class of file as regenerable output,
so tracking them contradicted the stated intent.

The `kg/` subtree is orphaned, not an alternate data directory: every script resolves
`DATA = ROOT / "data"` (`kg.py:13`, `build_kg.py:27`, `server.py`, `scripts/acceptance.py:30`),
and no code or doc references `kg/data/`. It is leftover output from a pipeline run made in the
wrong working directory.

Files remain on disk untouched; only tracking changed. Git history is not rewritten, so `.git`
still contains the blobs (~33 MB) and no force push is needed — a fresh clone simply no longer
checks out 60 MB of regenerable binaries.

## Layer

Repository.

## Contract impact

`none`. No schema, wire format, or runtime behavior changed. No code reads these paths.

## Files

- `git rm -r --cached backend/knowledge_graph/kg` — 24 files: `kg.graphml`, `embeddings/*`,
  `snapshots/v2/*`, `snapshots/v3/*`, `edges_candidates.csv.gz`, `reports/*`.
- `.gitignore` and `backend/knowledge_graph/.gitignore` — added type-based rules
  (`**/embeddings/`, `**/snapshots/`, `**/reports/`, `*.graphml`, `*.npy`, `*.idx`, `*.pt`,
  `**/edges_candidates.csv.gz`, `**/llm_clean_decisions*.jsonl`) alongside the existing
  path-anchored ones, so depth no longer determines whether an artifact is ignored.
- `backend/knowledge_graph/README.md` — documented that `data/` is the only artifact directory,
  that generated output is not committed, and how to regenerate everything. Also corrected the
  directory listing, which was stale: it named the root `kb/`, listed two files that do not
  exist (`READMD.md`, `scripts/_speed_test.py`), and omitted four that do (`turbo_clean.py`,
  `repair_coverage.py`, `finish_pipeline.py`, `_status.py`).

## Verification

Working directory `.` (repository root).

- `git ls-files backend/knowledge_graph/kg | wc -l` → `0` (was 24).
- `git ls-files -z | xargs -0 du -ck | tail -1` → `2701` KB (was `64037`).
- **No tracked file became ignored** — the risk when broadening patterns:
  `git ls-files | git check-ignore --stdin` → no output.
- All four artifact classes now ignored: `git check-ignore -q` returns true for
  `kg/data/embeddings/faiss.idx`, `kg/data/kg.graphml`, `kg/data/snapshots/v2/rotate.pt`,
  `kg/data/edges_candidates.csv.gz`.
- `git status --porcelain --untracked-files=all | grep '^??'` → no output. The eight
  `kg/data/reports/*.csv` files initially surfaced as untracked noise, which is why
  `**/reports/` was added.
- Input data still tracked and intact: `data/seed.csv`, `data/word_variants.csv`, `raw/*.csv`.
- `audit_repository.ps1` → `347 tracked files checked; repository audit passed`, exit 0.
- `release_readiness.ps1` → exit 0. Its `$retired` list contains `kg`, but it only inspects the
  **first** path segment (`$parts[0]`), which is `backend` here, so untracking this subtree does
  not trip it. Confirmed by the passing run.

Not run: `verify.ps1` component suites. No code, test, or dependency changed, and no test reads
these paths. The KG component has no automated tests at all (tracked separately).

## Rollback

`git revert` this commit to restore tracking; the files are still on disk, so nothing must be
regenerated. Reverting also restores the ignore gap, so the artifacts would be committable
again.

## Reusable knowledge

Not promoted to a skill; recorded here as the reusable lesson:

**A path-anchored ignore rule silently fails when the same artifact appears at another depth.**
The 50 MB per-file cap in `audit_repository.ps1` did not catch this either — the largest single
file is ~8 MB, so 60 MB accumulated under the limit. Size caps bound individual files, not
aggregate footprint, and neither bounds *type*.

Two mechanical follow-ups belong in the planned `audit_repository.ps1` extension: reject tracked
files matching these artifact types anywhere, and lower the per-file cap so this class cannot
reappear one 8 MB file at a time.
