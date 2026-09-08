# Change: Build and deploy the hardware-independent parent demo

**Commit binding:** Same commit as this record.

## Summary

Package the existing parent web and compiled Gateway behind a same-origin proxy.
Bind published traffic to loopback; expose truthful mock data and privacy limitations.
Add health checks, restart policies, deployment smoke checks and operating instructions.
Physical RDK X5 remains pending acceptance and is not required to start this release.

## Layer

Repository, Backend Service. No Agent or trust-boundary behavior changed.

## Contract impact

None.

## Files

`compose.yaml`, `deploy/`, `.dockerignore`, Gateway build config/package/start entry,
`scripts/deployment-smoke.mjs`, `.github/workflows/ci.yml`, README documentation.

## Verification

Gateway build and compiled dashboard request passed. Compose configuration validates.
Local built web smoke passed: HTML, JavaScript, health, dashboard and weekly report.
Docker Linux engine built both images; both containers healthy. Container smoke
passed on loopback port 8081. Browser rendered the dashboard with explicit mock and
device-offline labels. Repository audit passed for 413 tracked files.

## Rollback

Revert this change and rebuild the prior release. Demo state is in memory and resets
on restart; no persistent state migration is introduced.

## Reusable knowledge

See `playbooks/incidents/INC-0007-deployment-verification.md`.
