---
name: she-ios-soft-orbit
description: Use when creating or reviewing SwiftUI screens, components, motion, or visual states for the SHE iOS parent app.
---

# SHE iOS Soft Orbit

## Outcome

Make the parent app feel calm, precise, and relational: a light 3D 小P leads one clear parent task, while evidence remains readable and honest.

## Visual Contract

| Area | Requirement |
|---|---|
| Palette | Mist white surfaces, cool lavender pet/accent, deep ink text; one accent action per screen |
| Pet | Draw with SwiftUI gradients, highlights, overlays, and shadows; no raster pet or heavyweight 3D engine |
| Hierarchy | Pet First: greeting/device status → pet + one evidence-backed highlight → one task → exactly three metrics |
| Metrics | 主动开口、无提示输出、新词; move other metrics to Reports |
| Material | Airy translucent cards only where text contrast remains strong; provide opaque fallback |
| Shape | Generous space, consistent large radii, few containers, no rainbow KPI grid |

## Build Procedure

1. Read `clients/ios/SHEParentApp/Design/SoftOrbitTheme.swift` and reuse its semantic tokens.
2. Bind copy to typed API evidence. Never invent mastery, praise, device state, or “live” status.
3. Compose from existing `PetOrbView`, `GlassCard`, and `MetricTile` before adding a component.
4. Keep motion state-driven and restrained. Read `accessibilityReduceMotion`; stop breathing/parallax when enabled.
5. Use semantic fonts and flexible layout. Verify Dynamic Type, VoiceOver order, dark mode, reduced transparency, and 44-point controls.
6. Run the iOS source audit and XCTest commands documented in `clients/ios/README.md`.
7. Record the logical change in `playbooks/changes`.

## Stop Conditions

Stop and revise if a screen adds a second primary action, more than three Today metrics, fixed tiny type, looping bounce, decorative data, a raster pet, or color-only state.

## Quick Review

- One glance answers: what happened, what matters now, is the device okay?
- 小P is one accessible element with meaningful status text.
- Offline, empty, loading, and error states are gentle and explicit.
- Reduce Motion and reduced transparency produce complete, usable alternatives.
