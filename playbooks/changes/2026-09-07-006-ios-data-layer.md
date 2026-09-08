# Change 006 — iOS contract and data layer

Commit binding: same commit as this record

## Summary

Added the iOS 17 XcodeGen definition, contract-aligned Codable models, ephemeral
HTTP client, demo API, Keychain credential store, observable app state, and tests
for canonical fixture decoding, offline state, and optimistic-settings rollback.

## Layer

iOS parent-client domain and infrastructure. No teaching Agent or learner
mastery mutation is exposed.

## Contract impact

Consumes dashboard, weekly report, device settings, parent constraints, and
privacy responses at contract version `1.0`. Schemas remain unchanged.

## Files

- `clients/ios`
- `playbooks/changes/2026-09-07-006-ios-data-layer.md`

## Verification

Windows source/configuration audits are run locally. Swift, XcodeGen, build, and
XCTest are unavailable on this Windows host and must run in the macOS CI job
before iOS compilation can be claimed.

## Rollback

Revert this commit. The Release base URL intentionally points to the inert
`api.invalid` placeholder until an approved production endpoint exists.

## Reusable knowledge

Cross-platform fixtures stay the decoding truth; HTTP bodies are never logged;
only credentials enter Keychain; parent clients may update settings and
constraints but have no learner-mastery write API.
