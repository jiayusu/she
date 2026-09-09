# Change: Standardize component docs and give every service a unique port

**Commit binding:** Same commit as this record.

## Summary

Two defects that made an agent opening a component directory read false information:

1. **Five component READMEs were superseded PRDs.** `agents/director`, `backend/memory_store`,
   `backend/intel`, `backend/pointing`, and `agents/interaction` each led with a numbered PRD
   (`03 五大臣 Agent 调度 PRD · V1.0`) describing the five-minister architecture that
   `AGENTS.md` §28.3 explicitly forbids restoring. Three had no markdown headings at all and
   contained literal `表格` markers where tables had been lost. The first thing an agent read in
   those directories was a design it is not allowed to build.

   PRDs are archived under `docs/archive/prd/` (acceptance IDs FR-G01…, FR-M01…, FR-I01…,
   FR-P01…, FR-E01… preserved). Each component now has a README stating what it owns, how to
   run it, how to test it, and which contracts it touches — with commands taken from
   `package.json`, `pyproject.toml`, and `scripts/verify.ps1` rather than restated from memory.

2. **Three services defaulted to a port another service already claimed.** 8787 was claimed by
   `agents/director`, `backend/knowledge_graph`, and `backend/pointing`; 8788 by
   `backend/device_gateway` and `backend/intel`. Two of those could not run side by side without
   an override, and `agents/director` and `backend/pointing` even shared the variable name `PORT`.

   Kept: `knowledge_graph` 8787 (two services default `KG_URL` to it), `device_gateway` 8788
   (hardcoded in the iOS app and xcconfig), `memory_store` 8789 (no collision).
   Reassigned: `director` → **8790**, `intel` → **8791**, `pointing` → **8792**.
   This deliberately avoids touching 8788, so no iOS rebuild is required and nothing needs
   verifying on a platform unavailable here.

Doc layout is now uniform: `<component>/README.md` for 职责/运行/测试, `<component>/docs/design.md`
for detail. The three names previously used for the same concept (`IMPL.md`,
`IMPLEMENTATION.md`, `DESIGN.md`) and the two locations (root vs `docs/`) are gone.

## Layer

Repository, plus Backend Service (port defaults).

## Contract impact

`none`. No schema or wire format changed. Port defaults are configuration, and every service
keeps its existing environment variable (`PORT`, `INTEL_PORT`, `KG_PORT`, `STORE_PORT`), so any
deployment setting them explicitly is unaffected.

## Files

- Archived: `docs/archive/prd/{director,memory_store,intel,pointing,interaction}-prd-v1.md`.
- New READMEs: `agents/director`, `agents/interaction`, `backend/intel`, `backend/memory_store`,
  `backend/pointing`, `backend/device_gateway`, `clients/hardware-rx5`, `shared/contracts`
  (the last three had none at all).
- Renamed to `<component>/docs/design.md`: `backend/intel/IMPL.md`,
  `backend/memory_store/IMPLEMENTATION.md`, `agents/interaction/DESIGN.md`,
  `backend/pointing/docs/IMPLEMENTATION.md`.
- Deleted `agents/director/IMPLEMENTATION.md` — its quick-start and FR-verification table are
  folded into the new README, so the component no longer has two overlapping entry docs.
- Ports: `agents/director/src/index.ts`, `backend/pointing/server/server.js` (2 sites),
  `backend/intel/config.py`, `backend/intel/server.py`, `backend/intel/.env.example`, and the
  URLs in `agents/director/docs/api.md`, `backend/pointing/docs/design.md`,
  `backend/intel/docs/design.md`.
- `docs/IMPLEMENTATION_BACKLOG.md` — added the open cross-language contract-drift item.

## Verification

- **Ports are unique.** Each of the six services resolves to a distinct default:
  8787 `knowledge_graph`, 8788 `device_gateway`, 8789 `memory_store`, 8790 `director`,
  8791 `intel`, 8792 `pointing`. Confirmed by grepping the six defining lines.
- **No test depended on a default port** — every suite binds ephemeral port 0
  (`createServer({port: 0})`, `createGateway({port: 0})`), checked before changing anything.
- **Suites after the port change**, run from each component directory as `verify.ps1` does:
  `agents/director` 66 passed + typecheck clean; `backend/device_gateway` 10 passed + typecheck
  clean; `backend/intel` 27 passed; `backend/memory_store` 61 passed; `agents/interaction`
  103 passed and `scripts/validate_assets.py` 全部通过; `clients/hardware-rx5` 11 passed;
  `shared/contracts` 12 passed. `backend/pointing` 41/42 — the same pre-existing failure
  documented in the previous commit, unchanged by this one.
- **Every relative markdown link resolves** — all `[](…)` targets in tracked `.md` files outside
  `docs/archive/` checked programmatically, including the links the renames would have broken.
- **Every component has a README** — the 11 component directories checked in a loop.
- `audit_repository.ps1` → `360 tracked files checked; repository audit passed`, exit 0.
  `release_readiness.ps1` → exit 0.

Not verified here: iOS build/XCTest (requires macOS, Xcode, XcodeGen) — untouched by this
commit, since 8788 deliberately did not move. Physical RX5 remains hardware-gated.

## Rollback

`git revert` this commit. Ports return to their colliding defaults and the PRDs return to being
component READMEs. No state implications; no data migration either way.

## Reusable knowledge

Not a skill. Two lessons worth reusing:

**When a doc and the code disagree, check the code before copying the doc.** The KG README's
directory listing named a root that no longer exists and cited two files that were deleted while
omitting four that were added. Writing the new READMEs from `package.json` scripts and
`pyproject.toml` — rather than from the prose already in the repo — is what surfaced that.

**A README that forward-references planned work is a false claim the moment it is committed.**
The draft `shared/contracts/README.md` said the contract-drift gap was "已记入待办" when the
backlog contained no such item. Fixed by actually adding the backlog item, not by softening the
sentence. Same class of error as the self-matching verification line caught two commits ago:
prose about the repository has to be checked against the repository.
