# SHE implementation backlog

This is the delivery ledger for the real product path. Items marked **done** are
implemented in the repository and covered by the existing verification commands.
Items marked **hardware-gated** require physical RX5 access and must not be
represented as complete by the simulator.

## Product and learning architecture

- [done] Keep one child-facing Interaction Agent and expose `POST /agent/direct`
  as the learning-first orchestration boundary.
- [done] Add deterministic Learner Model, Curriculum, Scaffold, Story and
  Assessment components behind typed contracts.
- [done] Make `language_level` (L0-L5) and `scaffold_level` (S0-S6)
  separate across all boundaries, including the legacy interaction adapter.
- [done] Replace hard-coded target prompts with target-aware, child-safe
  patterns and make learner starting level an explicit profile setting.
- [done] Preserve candidate-vs-confirmed evidence semantics in director output.
- [done] Stop legacy interaction memory writes from implying confirmed
  mastery; writes must carry evidence status for the shared-state writer.
- [done] Normalize all child-age prompt assets to the 4-8 product range.

## Shared state and services

- [done] Keep memory and KG access behind service boundaries; no agent writes
  SQLite/FAISS directly.
- [done] Add a versioned shared learning-event contract for raw evidence,
  candidate updates and confirmed mastery promotion.
- [done] Keep Zhihu/data intelligence off the child real-time path and behind
  fetch → structure → sensitive filter → human approval → KG update → rollback.
- [open] Close the cross-language contract drift gap. `backend/device_gateway`
  (Ajv) and `clients/hardware-rx5` (`jsonschema`) validate
  `shared/contracts/v1/*.schema.json` at runtime, but three representations are
  hand-written and checked by nothing: `clients/ios/SHEParentApp/Domain/Models.swift`,
  `agents/director/src/learning-events.ts`, and `shared/contracts/learning_events.py`.
  A field rename in `learning-event.schema.json` would be caught only where a
  fixture happens to cover it. Add codegen, or a test that decodes every
  `v1/fixtures/valid/*.json` through each hand-written model.

## Device and operational path

- [done] Device Gateway is the sole hardware/software transport boundary.
- [done] RX5 runtime has a production WebSocket transport, bounded reconnect,
  persisted event sequencing, heartbeat, command expiry/target checks, and
  explicit capability-degradation events.
- [done] Server-owned Digital Twin endpoints and timeline are wired to gateway
  events, commands and disconnects.
- [hardware-gated] Validate physical RX5 SSH, camera, ALSA, GPIO and accelerator;
  simulator coverage cannot close this item.
- [done] Add an explicit hardware-to-software event/command handoff
  document with enrollment, reconnect, idempotency and rollback details.

## Parent app and productionization

- [done] iOS contracts, offline/error states, accessibility hooks and explicit
  mock privacy semantics are present.
- [done] Replace fixture-only learning/report data with a service adapter
  that can consume the shared learning-event/report contracts when a real backend
  is deployed. Keep the demo adapter clearly labelled until then.
- [done] Add release-readiness checks for stale legacy directory references,
  generated artifacts, secrets and unverified hardware claims.

## Verification

- [done] Existing platform-independent suites and type checks are wired in
  `scripts/verify.ps1`.
- [in progress] Re-run the full verification after the learning-contract changes.
- [hardware-gated] Run the RX5 first-boot playbook on a real board.

## Delivery rule

No item is called complete because a mock returned a plausible payload. A task is
complete only when the corresponding service boundary, failure path, persistence
semantics and verification evidence exist. Hardware-gated items remain visibly
open until physical validation is possible.
