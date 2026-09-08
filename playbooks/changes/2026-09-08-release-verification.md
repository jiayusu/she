# Change: Make web and cross-platform release verification executable

**Commit binding:** Same commit as this record.

## Summary

Fix Node wildcard test discovery on Windows. Repair web build aliases, unsupported
Vite configuration, canonical fixture/Gateway test paths and exact optional patch
properties. Include web tests/typecheck/build and Gateway build in verification.
Update stale pointing page-title tests and supply an explicit WebSocket test client.
Upgrade vulnerable web development dependencies; npm reports zero web vulnerabilities.

## Layer

Web, Repository. No shared schema or trust-boundary change.

## Contract impact

None; omitted patch properties remain absent.

## Files

`scripts/node-tests.mjs`, `scripts/verify.ps1`, component package manifests/lockfiles,
`clients/web/` configuration, decoder and tests; pointing server tests.

## Verification

Observed failures before fixes are in INC-0007. After fixes: Gateway 12 tests,
Director 66 tests, pointing 42 tests, intel 27 tests and web 15 tests pass;
web typecheck and build pass. The audit self-test checks committed HEAD; the
pre-existing missing web README requires this commit before its clean case passes.

## Rollback

Revert changes and reinstall dependencies using component lockfiles.

## Reusable knowledge

`playbooks/incidents/INC-0007-deployment-verification.md`; use automated checks.

Follow-up: use Select-String for the quoted iOS deployment-target check to avoid
Windows native argument quote stripping; preserve the required 17.0 target.
