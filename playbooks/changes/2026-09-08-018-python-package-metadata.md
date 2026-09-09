# Change: Add Python tooling metadata and remove `sys.path` hacks

**Commit binding:** Same commit as this record.

## Summary

Four Python components had no package metadata and imported their own code by mutating
`sys.path` inside `tests/conftest.py`. All four now have a `pyproject.toml`, and every
`sys.path` hack is gone — replaced by pytest's `pythonpath` setting.

**Deviation from the approved plan, and why.** The plan called for making all four components
`pip install -e`-able. Only `backend/memory_store` became installable. `backend/intel` and
`backend/knowledge_graph` are flat-module layouts whose top-level module names are generic —
`config`, `db`, `server`, `llm_client`, `pipeline` — and publishing them would put those names
in the site-packages top-level namespace, where:

- `llm_client` and `server` **collide between the two components**, and the two `llm_client.py`
  files are not identical (`fa40a0d5` vs `c9c91c0f`); and
- generic names like `config` and `db` can shadow, or be shadowed by, third-party packages.

Installing both would therefore produce a broken environment. Making them installable properly
means first moving their modules into a package directory (`intel/`, `knowledge_graph/`), which
is a source-layout refactor with real regression risk — out of scope for a docs-and-metadata
pass. The plan anticipated this ("若此步风险偏高，可仅补元数据"), so those two, plus
`shared/contracts`, get **tool-configuration-only** `pyproject.toml` files with no `[project]`
or `[build-system]` table, and a comment explaining what must happen before they can be packaged.
`shared/contracts` is excluded for a different reason: its source of truth is
`v1/*.schema.json` (data), and no component imports `learning_events.py`.

## Layer

Repository.

## Contract impact

`none`. No schema, wire format, or runtime behavior changed.

## Files

- `backend/memory_store/pyproject.toml` — **installable** as `she-memory-store`. Publishes only
  `memstore*`, so `server.py` and other top-level scripts are not exposed as modules.
  Dev deps in `[project.optional-dependencies]`.
- `backend/intel/pyproject.toml`, `backend/knowledge_graph/pyproject.toml`,
  `shared/contracts/pyproject.toml` — pytest config only, each documenting why it is not a package.
- `backend/intel/requirements-dev.txt` — new (`-r requirements.txt` plus pytest).
- `backend/memory_store/requirements.txt` — dropped `pytest>=8.0  # dev`, which was declared as
  an unconditional runtime dependency and so installed into production.
- `agents/interaction/pyproject.toml` — added `pythonpath = ["src"]`.
- `sys.path` mutations removed: `backend/memory_store/tests/conftest.py`,
  `backend/intel/tests/conftest.py` (kept `ROOT`, still used for `TEST_DATA`; dropped the now-unused
  `sys` import), `agents/interaction/tests/conftest.py`.
- `.github/workflows/ci.yml` — see below.
- `backend/{memory_store,intel,knowledge_graph}/README.md`, `shared/contracts/README.md` —
  install/test commands updated.
- `docs/IMPLEMENTATION_BACKLOG.md` — two open items added (see Reusable knowledge).

## Fixed a latent CI failure

Removing pytest from `backend/memory_store/requirements.txt` exposed an existing fragility:
`ci.yml` never installed pytest for `memory_store` or `intel` at all. It only worked because
line 31 installs `shared/contracts/requirements-dev.txt` first, which happens to include pytest —
an implicit install-order coupling that would break if that line were reordered or changed.

Now explicit per component:

```yaml
python -m pip install -e "$GITHUB_WORKSPACE/backend/memory_store[dev]"
python -m pip install -r "$GITHUB_WORKSPACE/backend/intel/requirements-dev.txt"
```

## Verification

Suites run from each component directory, and again with the Windows absolute path
`scripts/verify.ps1` actually passes, since `pythonpath` is resolved relative to the rootdir:

- `backend/memory_store` 61 passed (both invocation styles), with `conftest.py` no longer
  touching `sys.path`. `python -c "import server"` still succeeds from the component directory.
- `agents/interaction` 103 passed (both styles) + `scripts/validate_assets.py` 全部通过.
- `backend/intel` 27 passed.
- `shared/contracts` 12 passed + `validate_contracts.py` → `6 valid accepted, 5 invalid rejected`.
- `clients/hardware-rx5` 11 passed.
- `python -m pip install -e './backend/memory_store[dev]' --dry-run` resolves:
  `Would install Flask-3.1.3 … she-memory-store-1.0.0`.
- `audit_repository.ps1` → `369 tracked files checked; repository audit passed`, exit 0.
  `release_readiness.ps1` → exit 0.

Not verified: the changed `ci.yml` lines cannot run locally; they are the standard
`pip install -e '<dir>[dev]'` and `-r <file>` forms, and the editable install was dry-run checked
above. `backend/knowledge_graph` has no tests to run — that is why its pytest config is
untested and its `testpaths` points at a directory that does not exist yet.

## Rollback

`git revert` this commit. The `sys.path` hacks return, and CI reverts to obtaining pytest by
install-order luck. If only the packaging is unwanted, deleting
`backend/memory_store/pyproject.toml` requires restoring that component's `conftest.py` hack,
since imports would otherwise fail.

## Reusable knowledge

**A flat module layout is not safe to package.** The blocker was found by listing top-level
module names per component and diffing them, *before* writing any `[project]` table. Worth doing
for any flat-layout Python component: `ls *.py` and check the names against sibling components and
common third-party packages. The fix is a package directory, not a `pyproject.toml`.

**`pythonpath` replaces `sys.path` in conftest.** Available in pytest ≥ 7.0 (this repo has 8.4.2).
It is resolved from the rootdir, so it keeps working when tests are invoked by absolute path from
another directory — which is how `scripts/verify.ps1` calls them.

Two gaps were found while writing docs for these components and are now recorded in
`docs/IMPLEMENTATION_BACKLOG.md` rather than left as prose claims:

- `backend/knowledge_graph` has **no automated tests** — the only Python component with none, and
  absent from both `verify.ps1` and CI.
- The cross-language contract drift gap (hand-written Swift/TS/Python copies of
  `learning-event.schema.json` that nothing validates).

Both were written into a README first as "已记入待办" when no such item existed. Same error class
as the two earlier in this reorganization: **prose about the repository must be checked against the
repository.** Fixed by adding the items, not by softening the sentences.
