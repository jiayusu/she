# Change 012 — Soft Orbit feel pass: motion, haptics, and honest refresh

Commit binding: same commit as this record

## Summary

Rewrote the iOS presentation suite around a motion vocabulary: spring press
feedback with haptics on every accent action, staggered card entrances, a
blinking and breathing 小P, numeric roll-over on metric values, selection
haptics on tabs/sliders/steppers, a save state machine on parent goals, and a
stale-content banner. Failed pull-to-refresh now keeps existing evidence
instead of wiping the dashboard back to offline. The volume slider commits one
patch on release instead of firing a network patch per drag step.

## Layer

App (iOS presentation + view-model refresh policy). No teaching, assessment,
KG, or mastery behavior; `AppModel` still has no mastery mutation API.

## Contract impact

none. All displayed state remains typed contract-backed values; `refreshError`
is client-side UI state derived from existing `AppAPIError` cases.

## Files

- `A:\working\she\clients\ios\SHEParentApp\Design\SoftOrbitTheme.swift` — Motion presets, skeleton pulse, new AccessibilityCopy
- `A:\working\she\clients\ios\SHEParentApp\Components\SoftOrbitPrimaryButtonStyle.swift` — new
- `A:\working\she\clients\ios\SHEParentApp\Components\SoftOrbitEntrance.swift` — new
- `A:\working\she\clients\ios\SHEParentApp\Components\PetOrbView.swift` — blink loop, breathing shadow
- `A:\working\she\clients\ios\SHEParentApp\Components\MetricTile.swift` — numeric content transition
- `A:\working\she\clients\ios\SHEParentApp\Features\Today\TodayView.swift` — GlassCard hero, entrance cascade, stale banner, phase crossfade
- `A:\working\she\clients\ios\SHEParentApp\Features\Reports\ReportsView.swift` — entrance cascade
- `A:\working\she\clients\ios\SHEParentApp\Features\Device\DeviceView.swift` — commit-on-release slider, haptics
- `A:\working\she\clients\ios\SHEParentApp\Features\Profile\ProfileView.swift` — save state machine, haptics
- `A:\working\she\clients\ios\SHEParentApp\Features\RootTabView.swift` — selection haptic
- `A:\working\she\clients\ios\SHEParentApp\State\AppModel.swift` — stale-evidence refresh policy
- `A:\working\she\clients\ios\SHEParentAppTests\AppModelTests.swift` — two new refresh tests
- `A:\working\she\clients\ios\SHEParentAppTests\AccessibilityContractTests.swift` — new copy pinned

## Verification

Tests written first and now pass logically: `testFailedRefreshKeepsEvidenceAndReportsRefreshError`
(phase stays `.ready`, dashboard preserved, `refreshError == .offline`,
`transientError == nil`), `testRefreshWithEvidenceDoesNotDropBackToSkeleton`
(no `.loading` regressions during refresh), plus new copy pins. Source audits
from `A:\working\she\clients\ios\README.md` were run on this host:

- `rg -n 'accessibilityReduceMotion|accessibilityReduceTransparency|accessibilityLabel|dynamicTypeSize' SHEParentApp` — all four hooks present.
- `rg -n 'SceneKit|RealityKit|\.animation\([^,]+\)' SHEParentApp` — no matches; every animation is value-scoped and formatted so the audit stays mechanical.

XCTest/xcodebuild remain macOS CI work (no Xcode on this host); CI runs the
standard generate/build/test sequence.

## Rollback

Revert this commit. The domain/API layer and contract fixtures are untouched,
so the previous presentation layer restores cleanly.

## Reusable knowledge

No new incident. The existing skill `A:\working\she\skills\she-ios-soft-orbit\SKILL.md`
governed this pass; its stop conditions were re-checked (one primary action per
screen, three metrics, no looping bounce, no color-only state). One audit gotcha
worth remembering: the forbidden-pattern audit also matches `.animation(`
inside doc comments, so comments must not contain the literal sequence.
