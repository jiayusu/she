# System rearchitecture: role-based migration, Digital Twin, and Zhihu portal

## Outcome

Retired implementation paths were migrated into role-based locations. The Device Gateway now feeds a server-owned Digital Twin and exposes twin inspection, timeline, and command endpoints. The Zhihu intelligence service remains isolated from child realtime dialogue and now exposes the complete operator workflow, including auditable modify, radar-latest, and KG retry/flush operations.

## Canonical locations

- `agents/interaction`
- `agents/director`
- `backend/knowledge_graph`
- `backend/memory_store`
- `backend/pointing`
- `backend/intel`
- `backend/digital_twin`
- `backend/device_gateway`

## Verification

- `npm run typecheck` in `backend/device_gateway` passed.
- `git diff --check` passed.
- Full platform verification is run after dependency/path normalization; physical RX5 validation remains pending SSH access.

## Safety boundary

Zhihu content can reach the child product only through structure, sensitive filtering, human approval, KG hot update, and local retrieval. Digital Twin state contains operational metadata only and never raw media or child transcript content.
