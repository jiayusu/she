# Change: Make the parent web readable and usable

**Commit binding:** Same commit as this record.

## Summary

Replace the near-black accidental palette and narrow layout with readable warm
surfaces, responsive grids and large controls. Make the home action open a simple
shared preview; simplify reports, improve feedback, and restore actual saved family
plans rather than overwriting them with defaults.

## Layer

Web and Backend Service (GET parent constraints).

## Contract impact

Backward-compatible GET /v1/parent-constraints returns the existing ParentConstraints
v1 schema. No new fields. Existing write, privacy and device boundaries unchanged.

## Files

`clients/web/src/`, `clients/web/tests/parentExperience.test.tsx`, live API/model tests,
`backend/device_gateway/src/app.ts`, web test configuration and development lockfile.
Full screen-by-screen findings: `playbooks/changes/2026-09-08-parent-usability-review.md`.

## Verification

Before: home preview and saved-family UI tests failed; GET returned 404.
After: 18 web tests and 12 Gateway tests pass; both typechecks and web build pass.
Container and browser QA results appended after completion.

## Rollback

Revert this commit and rebuild Compose. No state migration; demo settings remain
in-memory and reset on Gateway restart.

## Reusable knowledge

CSS numeric RGB channels use a 0–255 range; use percentages or hex for 0–1 source
palettes. Keep this review as an incident/change record; no separate skill needed.
