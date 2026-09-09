# Change: add a read-only RPG quest card to the iOS parent app

**Commit binding:** Same commit as this record.

## Summary

Add an optional parent-facing view of the active `milk_picnic.v1` quest. The
iOS app now:

- reads `GET /v1/rpg/state` only when both child and session identities are
  explicitly supplied through build configuration;
- decodes finite node, phase, object, inventory, role, action, and delivery
  values and rejects a quest that violates the canonical v1 world snapshot;
- keeps quest refresh failure separate from the dashboard availability state;
- displays the current real-world role, waiting state, target expression, and
  virtual inventory in a clearly marked read-only card;
- exposes no API that advances a quest or changes world state, inventory, or
  learner mastery.

The feature is disabled by default in both Debug and Release configurations.

## Layer

App.

## Contract impact

None. The app consumes the existing backward-compatible
`rpg-quest-summary.schema.json` response without changing it.

## Files

- `clients/ios/SHEParentApp/Domain/Models.swift`
- `clients/ios/SHEParentApp/Networking/AppAPI.swift`
- `clients/ios/SHEParentApp/Networking/LiveAppAPI.swift`
- `clients/ios/SHEParentApp/Networking/MockAppAPI.swift`
- `clients/ios/SHEParentApp/State/AppModel.swift`
- `clients/ios/SHEParentApp/Features/Today/TodayView.swift`
- `clients/ios/SHEParentApp/App/SHEParentApp.swift`
- `clients/ios/SHEParentAppTests/ContractDecodingTests.swift`
- `clients/ios/SHEParentAppTests/AppModelTests.swift`
- `clients/ios/Config/Debug.xcconfig`
- `clients/ios/Config/Release.xcconfig`
- `clients/ios/project.yml`
- `clients/ios/README.md`
- `docs/architecture/07-parent-app.md`

## Verification

Not run, following the user's explicit instruction to edit files without
running tests, builds, lint, typechecks, audit scripts, or other verification
commands. Contract-decoding, identity rejection, and AppModel quest-loading
test sources were added for a later macOS verification run.

## Rollback

Remove the RPG domain contract models, `questState` API method, optional identity
configuration, AppModel quest fields, and Today quest card together. No server
or persisted-state migration is required because this change is read-only.

## Reusable knowledge

Parent visibility is a projection, not another game engine. Keep identity
configuration explicit, tolerate an unavailable quest projection without
blanking the rest of the dashboard, and never infer or mutate the next node in
the client.
