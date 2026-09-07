# SHE Cross-Platform Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an iOS 17 parent app, a deterministic Device Gateway, and an RDK X5 Ubuntu 22 runtime/simulator that communicate through versioned contracts and are maintained through project playbooks and reusable skills.

**Architecture:** JSON Schema files under `A:\working\she\shared\contracts\v1` are the cross-platform source of truth. A Node 20 TypeScript gateway exposes parent HTTP APIs and device WebSocket sessions; a Python runtime isolates X5 hardware behind ports and supplies a simulator; a SwiftUI app consumes the HTTP contracts through a replaceable API client and renders the approved Soft Orbit, Pet First experience.

**Tech Stack:** JSON Schema 2020-12, Node.js 20, TypeScript, `ws`, Ajv, Python 3.10+, `pytest`, `websockets`, Swift 5.9+, SwiftUI, XCTest, XcodeGen, GitHub Actions.

**Spec:** `A:\working\she\docs\superpowers\specs\2026-09-07-vertical-slice-design.md`

## Global Constraints

- The iOS deployment target is iOS 17; iPhone is primary and iPad must adapt.
- The first release has no login and uses one explicitly labeled demo family profile.
- Existing `engine`, `kg`, `store`, `po`, `route`, and `zhihu` directories remain in place.
- Cameras open only after an explicit event and always close when the capture window ends.
- Raw child audio, video, utterances, credentials, databases, model artifacts, and generated logs must not enter Git or default logs.
- App and device code never infer or directly mutate learner mastery.
- Every logical change ships with a structured file under `A:\working\she\playbooks\changes`.
- Known incidents and matching skills must be searched before diagnosing a repeated failure.
- Hardware-dependent behavior remains unverified until an actual RDK X5 is reachable by SSH.
- All commands and file references used during execution must use absolute paths.

---

### Task 1: Repository Governance, Playbooks, and Project Skills

**Files:**
- Create: `A:\working\she\.gitignore`
- Modify: `A:\working\she\AGENTS.md`
- Create: `A:\working\she\playbooks\README.md`
- Create: `A:\working\she\playbooks\templates\change.md`
- Create: `A:\working\she\playbooks\templates\incident.md`
- Create: `A:\working\she\playbooks\templates\decision.md`
- Create: `A:\working\she\playbooks\changes\2026-09-07-001-repository-governance.md`
- Create: `A:\working\she\playbooks\decisions\ADR-0001-contract-first-vertical-slice.md`
- Create: `A:\working\she\skills\she-contract-change\SKILL.md`
- Create: `A:\working\she\skills\she-incident-recovery\SKILL.md`
- Create: `A:\working\she\skills\she-ios-soft-orbit\SKILL.md`

**Interfaces:**
- Consumes: the approved spec and existing project-level rules in `A:\working\she\AGENTS.md`.
- Produces: mandatory change/incident formats and three reusable workflows referenced by later tasks.

- [ ] **Step 1: Add repository exclusion rules before staging the existing baseline**

Create a root `.gitignore` that excludes at minimum:

```gitignore
.env
.env.*
!.env.example
.superpowers/
**/node_modules/
**/__pycache__/
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.venv/
**/DerivedData/
**/.build/
**/xcuserdata/
*.db
*.db-*
*.sqlite
*.sqlite3
*.log
*.pid
kg/raw/conceptnet-assertions-5.7.0.csv.gz
kg/data/embeddings/
kg/data/snapshots/
kg/data/reports/
kg/data/edges_candidates.csv.gz
route/data/audit/
route/data/reports/
route/data/snapshots/
route/data/stores/
po/data/*.jsonl
zhihu/data/
clients/hardware-rx5/.state/
```

- [ ] **Step 2: Create the structured playbook templates**

Each change record must contain `Summary`, `Layer`, `Contract impact`, `Files`, `Verification`, `Rollback`, and `Reusable knowledge`. Each incident must contain `Fingerprint`, `Environment`, `Symptoms`, `Root cause`, `Attempts that did not work`, `Resolution`, `Verification`, `Prevention`, and `Skill decision`. Use `Commit binding: same commit as this record` instead of an unknown hash.

- [ ] **Step 3: Create the three project skills using skill-creator and writing-skills**

Each `SKILL.md` must include a narrow trigger, inputs, ordered procedure, stop conditions, verification, and pointers to the applicable playbook template. `she-contract-change` enforces Schema → fixtures → Gateway → RX5 → iOS. `she-incident-recovery` searches `A:\working\she\playbooks\incidents` and `A:\working\she\skills` before diagnosis. `she-ios-soft-orbit` enforces tokens, Pet First hierarchy, Dynamic Type, VoiceOver, and Reduce Motion.

- [ ] **Step 4: Extend AGENTS.md with the approved operating discipline**

Append a repository workflow section that mandates layer identification, pre-change skill/incident lookup, per-change records, evidence-backed incident resolution, skill promotion criteria, absolute paths, and the rule that unverified RX5 procedures remain playbooks rather than skills.

- [ ] **Step 5: Verify the ignore and governance rules**

Run:

```powershell
git -C 'A:\working\she' check-ignore 'A:\working\she\kg\raw\conceptnet-assertions-5.7.0.csv.gz'
git -C 'A:\working\she' check-ignore 'A:\working\she\route\node_modules\typescript\package.json'
rg -n 'T[B]D|T[O]DO|implement\s+later' 'A:\working\she\playbooks' 'A:\working\she\skills'
```

Expected: both large/generated paths are ignored and the placeholder scan has no matches.

- [ ] **Step 6: Stage the safe repository baseline and audit it**

Run:

```powershell
git -C 'A:\working\she' add --all
git -C 'A:\working\she' diff --cached --check
git -C 'A:\working\she' ls-files | Select-String -Pattern '(node_modules|__pycache__|\.env$|\.db$|conceptnet-assertions)'
git -C 'A:\working\she' ls-files | ForEach-Object { Get-Item -LiteralPath (Join-Path 'A:\working\she' $_) } | Where-Object Length -gt 50MB
```

Expected: `diff --check` passes; secret/generated pattern scan and files-over-50-MB scan return no tracked files.

- [ ] **Step 7: Commit**

```powershell
git -C 'A:\working\she' commit -m 'chore: establish repository governance baseline'
```

---

### Task 2: Versioned Shared Contracts and Fixtures

**Files:**
- Create: `A:\working\she\shared\contracts\v1\contract-version.json`
- Create: `A:\working\she\shared\contracts\v1\device-event.schema.json`
- Create: `A:\working\she\shared\contracts\v1\device-command.schema.json`
- Create: `A:\working\she\shared\contracts\v1\dashboard-snapshot.schema.json`
- Create: `A:\working\she\shared\contracts\v1\weekly-report.schema.json`
- Create: `A:\working\she\shared\contracts\v1\parent-constraints.schema.json`
- Create: `A:\working\she\shared\contracts\v1\device-settings.schema.json`
- Create: `A:\working\she\shared\contracts\v1\fixtures\valid\*.json`
- Create: `A:\working\she\shared\contracts\v1\fixtures\invalid\*.json`
- Create: `A:\working\she\shared\contracts\validate_contracts.py`
- Create: `A:\working\she\shared\contracts\requirements-dev.txt`
- Create: `A:\working\she\shared\contracts\tests\test_contracts.py`
- Create: `A:\working\she\playbooks\changes\2026-09-07-002-shared-contracts.md`

**Interfaces:**
- Consumes: contract ordering rules from `A:\working\she\skills\she-contract-change\SKILL.md`.
- Produces: contract version string `1.0`, schemas with `additionalProperties: false`, and canonical fixtures consumed verbatim by Gateway, Python, and Swift tests.

- [ ] **Step 1: Write failing contract tests**

The test must pair each valid fixture with its schema and assert every invalid fixture yields at least one validation error:

```python
def test_valid_fixtures_match_schema(contract_case):
    schema, payload = contract_case
    Draft202012Validator(schema).validate(payload)

def test_invalid_fixtures_are_rejected(invalid_contract_case):
    schema, payload = invalid_contract_case
    assert list(Draft202012Validator(schema).iter_errors(payload))
```

- [ ] **Step 2: Run tests and confirm failure**

```powershell
python -m pytest 'A:\working\she\shared\contracts\tests' -q
```

Expected: FAIL because schemas and fixtures do not yet exist.

- [ ] **Step 3: Implement schemas and canonical fixtures**

Use RFC 3339 UTC timestamps, UUID strings for event/command IDs, non-negative monotonically increasing sequence numbers, explicit enums, numeric bounds for volume/confidence, and `mock: true` on all demo learning/report responses. Invalid fixtures must cover missing version, unknown event type, out-of-range volume, extra properties, and a long-term learner claim without evidence.

- [ ] **Step 4: Add the standalone validator**

`validate_contracts.py` must load every valid and invalid fixture, print one summary line, and exit non-zero on an unexpected validation result. It must not rewrite fixtures.

- [ ] **Step 5: Run and verify**

```powershell
python -m pip install -r 'A:\working\she\shared\contracts\requirements-dev.txt'
python -m pytest 'A:\working\she\shared\contracts\tests' -q
python 'A:\working\she\shared\contracts\validate_contracts.py'
```

Expected: all tests pass and validator reports all cases accepted/rejected as expected.

- [ ] **Step 6: Commit**

```powershell
git -C 'A:\working\she' add -- 'shared/contracts' 'playbooks/changes/2026-09-07-002-shared-contracts.md'
git -C 'A:\working\she' commit -m 'feat: define cross-platform v1 contracts'
```

---

### Task 3: Deterministic Device Gateway

**Files:**
- Create: `A:\working\she\backend\device_gateway\package.json`
- Create: `A:\working\she\backend\device_gateway\package-lock.json`
- Create: `A:\working\she\backend\device_gateway\tsconfig.json`
- Create: `A:\working\she\backend\device_gateway\src\types.ts`
- Create: `A:\working\she\backend\device_gateway\src\contracts.ts`
- Create: `A:\working\she\backend\device_gateway\src\demo-repository.ts`
- Create: `A:\working\she\backend\device_gateway\src\device-sessions.ts`
- Create: `A:\working\she\backend\device_gateway\src\app.ts`
- Create: `A:\working\she\backend\device_gateway\src\index.ts`
- Create: `A:\working\she\backend\device_gateway\test\http.test.ts`
- Create: `A:\working\she\backend\device_gateway\test\device-session.test.ts`
- Create: `A:\working\she\backend\device_gateway\test\contracts.test.ts`
- Create: `A:\working\she\playbooks\changes\2026-09-07-003-device-gateway.md`

**Interfaces:**
- Consumes: v1 Schema and valid fixtures from `A:\working\she\shared\contracts\v1`.
- Produces: `createGateway(options): Promise<GatewayHandle>`, HTTP routes from the spec, and `WS /v1/device/session` with validated `DeviceEvent`/`DeviceCommand` messages.

- [ ] **Step 1: Write failing HTTP and repository tests**

Cover `/health`, dashboard, weekly report, device get/patch, parent constraints, privacy export, privacy erase, unknown route, invalid JSON, invalid settings, and the requirement that privacy responses include `mock: true` and never claim a real store mutation.

- [ ] **Step 2: Write failing WebSocket session tests**

Use an ephemeral port and assert: device hello marks it online, duplicate `event_id` is acknowledged once, lower `sequence` is rejected, incompatible contract version yields `contract_version_unsupported`, command acknowledgements correlate by ID, and disconnect marks the device offline.

- [ ] **Step 3: Confirm tests fail**

```powershell
Set-Location -LiteralPath 'A:\working\she\backend\device_gateway'
npm install
npm test
```

Expected: FAIL because gateway modules are absent.

- [ ] **Step 4: Implement schema loading and typed demo repository**

Ajv must compile the checked-in schemas. `DemoRepository` returns immutable copies of canonical demo data and permits only device settings and parent constraints to change in memory.

- [ ] **Step 5: Implement HTTP routes with explicit JSON errors**

Every response includes `contract_version: "1.0"`. Errors use `{ "error": { "code": string, "message": string } }`; no stack traces or payload dumps reach clients.

- [ ] **Step 6: Implement WebSocket sessions**

`DeviceSessionRegistry` stores current device connection, last sequence, bounded recent event IDs, heartbeat timestamp, and pending command acknowledgements. Bound the idempotency set to prevent unbounded memory growth.

- [ ] **Step 7: Run tests and typecheck**

```powershell
Set-Location -LiteralPath 'A:\working\she\backend\device_gateway'
npm test
npm run typecheck
```

Expected: both commands pass.

- [ ] **Step 8: Commit**

```powershell
git -C 'A:\working\she' add -- 'backend/device_gateway' 'playbooks/changes/2026-09-07-003-device-gateway.md'
git -C 'A:\working\she' commit -m 'feat: add deterministic device gateway'
```

---

### Task 4: RDK X5 Runtime and Simulator

**Files:**
- Create: `A:\working\she\clients\hardware-rx5\pyproject.toml`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\contracts.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\ports.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\fallback.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\redaction.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\runtime.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\adapters\simulator.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\adapters\rdk_x5.py`
- Create: `A:\working\she\clients\hardware-rx5\src\she_device\cli.py`
- Create: `A:\working\she\clients\hardware-rx5\deploy\she-device.service`
- Create: `A:\working\she\clients\hardware-rx5\scripts\install.sh`
- Create: `A:\working\she\clients\hardware-rx5\scripts\preflight.sh`
- Create: `A:\working\she\clients\hardware-rx5\tests\test_runtime.py`
- Create: `A:\working\she\clients\hardware-rx5\tests\test_redaction.py`
- Create: `A:\working\she\clients\hardware-rx5\tests\test_rdk_capabilities.py`
- Create: `A:\working\she\playbooks\releases\rx5-first-boot.md`
- Create: `A:\working\she\playbooks\changes\2026-09-07-004-rx5-runtime.md`

**Interfaces:**
- Consumes: canonical `DeviceEvent` and `DeviceCommand` fixtures.
- Produces: `DeviceRuntime.run()`, ports for camera/audio/GPIO/transport, `python -m she_device.cli simulate`, and a disabled-by-default `rdk` mode with capability discovery.

- [ ] **Step 1: Write failing runtime safety tests**

Tests must assert explicit `capture` opens the simulated camera, success and exception paths both close it, an unsolicited camera call never occurs, disconnect triggers local fallback, repeated commands are idempotent, and logs redact utterance/audio/image/token fields.

- [ ] **Step 2: Write failing RDK capability tests**

Mock imports and subprocess results to verify missing `srcampy`, `hbm_runtime`, `Hobot.GPIO`, `arecord`, or `aplay` produce structured unavailable capabilities rather than crashes or fake success.

- [ ] **Step 3: Confirm tests fail**

```powershell
python -m pip install -e 'A:\working\she\clients\hardware-rx5[dev]'
python -m pytest 'A:\working\she\clients\hardware-rx5\tests' -q
```

Expected: FAIL because the package is incomplete.

- [ ] **Step 4: Implement contracts, ports, fallback, and redaction**

Use dataclasses/enums and standard-library logging. The safe local fallback text is fixed and non-instructional: `"小P在这里，我们稍后再试一次。"` The redactor keeps event type, IDs shortened to eight characters, capability names, and error codes only.

- [ ] **Step 5: Implement runtime and simulator**

Handle command validation, sequence tracking, capture lifetime, playback, LED changes, acknowledgement, heartbeat, and exponential reconnect with bounded jitter. Simulator events must be deterministic under an injected clock/random source.

- [ ] **Step 6: Implement guarded RDK adapters and deployment files**

The camera adapter references `srcampy.Camera`; inference references `hbm_runtime`; GPIO references `Hobot.GPIO`; audio invokes ALSA through argument arrays without shell interpolation. `preflight.sh` reports OS, architecture, RDK packages, camera devices, ALSA devices, GPIO import, and network without changing pinmux or device state.

- [ ] **Step 7: Run tests**

```powershell
python -m pytest 'A:\working\she\clients\hardware-rx5\tests' -q
python -m she_device.cli simulate --once
```

Expected: tests pass and the simulator prints a redacted lifecycle ending in a command acknowledgement.

- [ ] **Step 8: Commit**

```powershell
git -C 'A:\working\she' add -- 'clients/hardware-rx5' 'playbooks/releases/rx5-first-boot.md' 'playbooks/changes/2026-09-07-004-rx5-runtime.md'
git -C 'A:\working\she' commit -m 'feat: add RDK X5 runtime and simulator'
```

---

### Task 5: Gateway-to-Device End-to-End Smoke Test

**Files:**
- Create: `A:\working\she\backend\device_gateway\test\device-e2e.test.ts`
- Create: `A:\working\she\clients\hardware-rx5\scripts\gateway_smoke.py`
- Create: `A:\working\she\playbooks\changes\2026-09-07-005-device-e2e.md`

**Interfaces:**
- Consumes: `createGateway`, v1 fixtures, and Python simulator transport behavior.
- Produces: a repeatable smoke path for online → wake → capture → pointing → speak → acknowledgement.

- [ ] **Step 1: Write the failing cross-process smoke assertion**

The TypeScript test starts Gateway on an ephemeral port, launches the Python script with the absolute WebSocket URL, waits for the ordered event sequence, sends `capture` and `speak`, and asserts both acknowledgements before a 10-second deadline.

- [ ] **Step 2: Confirm the smoke test fails**

```powershell
Set-Location -LiteralPath 'A:\working\she\backend\device_gateway'
npm test -- --test-name-pattern='Python RX5 simulator'
```

Expected: FAIL because `gateway_smoke.py` does not yet implement the protocol.

- [ ] **Step 3: Implement the narrow Python smoke client**

The script must use the production simulator package, accept only `--url` and `--device-id`, send canonical fixtures, and exit non-zero on timeout, schema error, or missing acknowledgement.

- [ ] **Step 4: Run the smoke test and full component suites**

```powershell
Set-Location -LiteralPath 'A:\working\she\backend\device_gateway'
npm test
python -m pytest 'A:\working\she\clients\hardware-rx5\tests' -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git -C 'A:\working\she' add -- 'backend/device_gateway/test/device-e2e.test.ts' 'clients/hardware-rx5/scripts/gateway_smoke.py' 'playbooks/changes/2026-09-07-005-device-e2e.md'
git -C 'A:\working\she' commit -m 'test: cover gateway and RX5 vertical flow'
```

---

### Task 6: iOS Domain, API Client, and Contract Tests

**Files:**
- Create: `A:\working\she\clients\ios\project.yml`
- Create: `A:\working\she\clients\ios\Config\Debug.xcconfig`
- Create: `A:\working\she\clients\ios\Config\Release.xcconfig`
- Create: `A:\working\she\clients\ios\SHEParentApp\App\SHEParentApp.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Domain\Models.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Networking\AppAPI.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Networking\LiveAppAPI.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Networking\MockAppAPI.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Security\KeychainStore.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\State\AppModel.swift`
- Create: `A:\working\she\clients\ios\SHEParentAppTests\ContractDecodingTests.swift`
- Create: `A:\working\she\clients\ios\SHEParentAppTests\AppModelTests.swift`
- Create: `A:\working\she\playbooks\changes\2026-09-07-006-ios-data-layer.md`

**Interfaces:**
- Consumes: valid dashboard, report, settings, and parent constraint fixtures.
- Produces: `protocol AppAPI`, `LiveAppAPI`, `MockAppAPI`, `@Observable @MainActor AppModel`, Codable domain models, and a Keychain-backed credential store.

- [ ] **Step 1: Write failing Swift decoding and AppModel tests**

Tests load copied canonical fixtures and assert exact snake-case mappings, `mock == true`, mastery-state enum values, loading/success/offline states, settings rollback on failed PATCH, and no persistence of mastery in App storage.

- [ ] **Step 2: Create the XcodeGen project definition**

Set `IPHONEOS_DEPLOYMENT_TARGET: 17.0`, Swift 5.9, bundle identifier `com.jiayusu.she.parent`, app and unit-test targets, fixture resources, and Debug `API_BASE_URL=http://127.0.0.1:8788` supplied through xcconfig rather than source.

- [ ] **Step 3: Implement Codable models and API abstraction**

`LiveAppAPI` uses an ephemeral `URLSessionConfiguration`, validates 2xx responses, rejects mismatched `contract_version`, decodes structured errors, and never logs bodies. `MockAppAPI` returns the same canonical semantic values as fixtures.

- [ ] **Step 4: Implement Keychain and observable state**

Keychain stores only device/API credentials. `AppModel` owns screen state and calls `AppAPI`; it does not expose a method that directly edits mastery.

- [ ] **Step 5: Run platform-independent checks**

```powershell
rg -n 'IPHONEOS_DEPLOYMENT_TARGET: 17\.0|contract_version|protocol AppAPI|@Observable' 'A:\working\she\clients\ios'
rg -n 'UserDefaults.*mastery|print\(.*response|T[O]DO|T[B]D' 'A:\working\she\clients\ios'
```

Expected: required patterns exist; forbidden/placeholder scan has no matches.

- [ ] **Step 6: Commit**

```powershell
git -C 'A:\working\she' add -- 'clients/ios' 'playbooks/changes/2026-09-07-006-ios-data-layer.md'
git -C 'A:\working\she' commit -m 'feat: add iOS contract and data layer'
```

---

### Task 7: Soft Orbit, Pet First SwiftUI Experience

**Files:**
- Create: `A:\working\she\clients\ios\SHEParentApp\Design\SoftOrbitTheme.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Components\PetOrbView.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Components\GlassCard.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Components\MetricTile.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Features\RootTabView.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Features\Today\TodayView.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Features\Reports\ReportsView.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Features\Device\DeviceView.swift`
- Create: `A:\working\she\clients\ios\SHEParentApp\Features\Profile\ProfileView.swift`
- Create: `A:\working\she\clients\ios\SHEParentAppTests\AccessibilityContractTests.swift`
- Create: `A:\working\she\clients\ios\README.md`
- Create: `A:\working\she\playbooks\changes\2026-09-07-007-ios-soft-orbit-ui.md`

**Interfaces:**
- Consumes: `AppModel` states and `she-ios-soft-orbit` skill.
- Produces: four-tab SwiftUI app, reusable theme/components, accessible labels, and deterministic previews using `MockAppAPI`.

- [ ] **Step 1: Write failing accessibility contract tests**

Tests assert the three dashboard metric labels, device privacy controls, destructive erase label, and pet summary are provided by centralized accessibility-copy constants. The source audit must assert animated components read `accessibilityReduceMotion`.

- [ ] **Step 2: Implement visual tokens and reusable primitives**

Define semantic light/dark colors, spacing scale, corner radii, shadows, type styles, and motion durations. `GlassCard` must preserve contrast with an opaque fallback under increased contrast/reduced transparency.

- [ ] **Step 3: Implement PetOrbView**

Use layered `RadialGradient`, highlights, inner-style overlays, and subtle shadow. Breathing animation pauses under Reduce Motion and the pet is exposed as one accessibility element with a meaningful status label.

- [ ] **Step 4: Implement Pet First Today view**

Render greeting/device state, pet and one evidence-backed highlight, one task, then exactly three metric tiles. Provide skeleton, offline, empty, and retry states without blaming the child.

- [ ] **Step 5: Implement Reports, Device, and Profile**

Reports show evidence and trends without scores for the child. Device updates settings optimistically but rolls back on API failure. Profile clearly labels the demo family, edits parent constraints, and requires confirmation before mock export/erase actions.

- [ ] **Step 6: Run source and configuration verification**

```powershell
rg -n 'accessibilityReduceMotion|accessibilityLabel|dynamicTypeSize|TodayView|ReportsView|DeviceView|ProfileView' 'A:\working\she\clients\ios\SHEParentApp'
rg -n 'SceneKit|RealityKit|\.animation\([^,]+\)' 'A:\working\she\clients\ios\SHEParentApp'
```

Expected: required accessibility/state patterns exist; no heavyweight 3D import or unscoped implicit animation appears.

- [ ] **Step 7: Commit**

```powershell
git -C 'A:\working\she' add -- 'clients/ios' 'playbooks/changes/2026-09-07-007-ios-soft-orbit-ui.md'
git -C 'A:\working\she' commit -m 'feat: build Soft Orbit parent experience'
```

---

### Task 8: CI, Full Verification, and GitHub Delivery

**Files:**
- Create: `A:\working\she\.github\workflows\ci.yml`
- Create: `A:\working\she\scripts\verify.ps1`
- Create: `A:\working\she\scripts\audit_repository.ps1`
- Create: `A:\working\she\README.md`
- Create: `A:\working\she\playbooks\releases\github-first-release.md`
- Create: `A:\working\she\playbooks\changes\2026-09-07-008-ci-delivery.md`

**Interfaces:**
- Consumes: every component test command and repository governance rule.
- Produces: one local verification entry point, one repository audit entry point, Ubuntu CI, macOS iOS CI, and the first complete push to `https://github.com/jiayusu/she.git`.

- [ ] **Step 1: Write the local verification and audit scripts**

`verify.ps1` runs contract, Gateway, RX5, existing engine/store/route/po/zhihu tests with explicit working directories and records skipped suites with reasons. `audit_repository.ps1` fails on tracked secret files, sensitive extensions, generated directories, files over 50 MB, merge markers, or staged whitespace errors.

- [ ] **Step 2: Add CI**

Ubuntu jobs install Python/Node dependencies and run all platform-independent suites. The macOS job installs XcodeGen, generates the project, selects an available iOS 17+ simulator dynamically, runs `xcodebuild build` and `xcodebuild test`, and uploads `.xcresult` only on failure. No secret is required.

- [ ] **Step 3: Add root README and release playbook**

Document component boundaries, absolute local commands, simulator quick start, iOS generation/build steps, known unverified RDK items, playbook/skill workflow, and privacy red lines.

- [ ] **Step 4: Run full local verification**

```powershell
& 'A:\working\she\scripts\verify.ps1'
& 'A:\working\she\scripts\audit_repository.ps1'
git -C 'A:\working\she' diff --check
git -C 'A:\working\she' status --short
```

Expected: verification and audit pass; status contains only intended Task 8 changes.

- [ ] **Step 5: Commit delivery infrastructure**

```powershell
git -C 'A:\working\she' add -- '.github/workflows/ci.yml' 'scripts' 'README.md' 'playbooks/releases/github-first-release.md' 'playbooks/changes/2026-09-07-008-ci-delivery.md'
git -C 'A:\working\she' commit -m 'ci: verify and document vertical slice'
```

- [ ] **Step 6: Perform final evidence-based review**

Run `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`. Resolve findings, rerun `A:\working\she\scripts\verify.ps1` and `A:\working\she\scripts\audit_repository.ps1`, and ensure `git -C 'A:\working\she' status --short` is empty.

- [ ] **Step 7: Configure remote and push**

```powershell
git -C 'A:\working\she' remote add origin 'https://github.com/jiayusu/she.git'
git -C 'A:\working\she' push -u origin main
```

If `origin` already exists, verify `git -C 'A:\working\she' remote get-url origin` exactly matches the approved URL before pushing. Do not force-push.

- [ ] **Step 8: Verify remote state**

```powershell
git -C 'A:\working\she' ls-remote --heads origin main
git -C 'A:\working\she' status --short --branch
```

Expected: remote `main` resolves to local `HEAD`, and the local branch is clean and tracking `origin/main`.
