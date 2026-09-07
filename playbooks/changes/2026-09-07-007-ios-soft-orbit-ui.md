# Change 007 — Soft Orbit, Pet First iOS experience

Commit binding: same commit as this record

## Summary

Implemented the approved four-tab parent experience with a pure SwiftUI light-3D
小P, Pet First Today hierarchy, exactly three metrics, evidence-centered reports,
safe device settings, and explicitly mock privacy controls.

## Layer

iOS presentation. It consumes typed app state and does not create teaching,
assessment, or learner-state decisions.

## Contract impact

No Schema change. All displayed evidence, device state, tasks, and metrics are
bound to contract-backed `AppModel` values.

## Files

- `A:\working\she\clients\ios\SHEParentApp\Design`
- `A:\working\she\clients\ios\SHEParentApp\Components`
- `A:\working\she\clients\ios\SHEParentApp\Features`
- `A:\working\she\clients\ios\SHEParentAppTests\AccessibilityContractTests.swift`
- `A:\working\she\clients\ios\README.md`

## Verification

The project skill `A:\working\she\skills\she-ios-soft-orbit\SKILL.md` governed
the implementation. Windows source audits cover hierarchy dependencies,
accessibility hooks, heavyweight 3D imports, and unscoped animation. Build and
XCTest remain for macOS CI because Xcode is unavailable on this host.

## Rollback

Revert this commit; the preceding iOS domain/API layer remains independently
usable.

## Reusable knowledge

Soft Orbit works best when the pet is code-native and relational, while metrics
stay few and evidence-bound. Reduced motion stops breathing; reduced transparency
and increased contrast switch cards to opaque semantic surfaces.
