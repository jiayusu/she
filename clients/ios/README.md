# SHE iOS parent app

The app targets iOS 17 and uses XcodeGen so the project file is reproducible.
It is a single explicitly labeled demo family with no login. The visual system is
Soft Orbit: a pure SwiftUI light-3D 小P leads the Today screen, followed by one
task and exactly three learning metrics.

## Generate and test on macOS

```bash
cd /absolute/path/to/she/clients/ios
brew install xcodegen
xcodegen generate --spec /absolute/path/to/she/clients/ios/project.yml
xcodebuild -project /absolute/path/to/she/clients/ios/SHEParentApp.xcodeproj -scheme SHEParentApp -sdk iphonesimulator build
xcodebuild -project /absolute/path/to/she/clients/ios/SHEParentApp.xcodeproj -scheme SHEParentApp -destination 'platform=iOS Simulator,name=iPhone 16' test
```

Use the repository's actual absolute path in place of `/absolute/path/to/she`.
The CI workflow dynamically selects an installed iOS 17+ simulator.

## Local Gateway

Debug reads `http://127.0.0.1:8788` from
`clients/ios/Config/Debug.xcconfig`; the value is injected into
Info.plist and is not hard-coded in the API client. Release intentionally uses
the inert `api.invalid` domain until a production endpoint is approved.

## Accessibility and privacy audit

```powershell
rg -n 'accessibilityReduceMotion|accessibilityReduceTransparency|accessibilityLabel|dynamicTypeSize' 'clients/ios/SHEParentApp'
rg -n 'SceneKit|RealityKit|\.animation\([^,]+\)' 'clients/ios/SHEParentApp'
```

The first command must find all four accessibility hooks. The second must return
no matches. The app never edits learner mastery; raw response bodies are not
logged; demo privacy actions explicitly report that the real store was not
mutated.
