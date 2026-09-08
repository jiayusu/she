# Learning contract and deterministic agent components

## Implemented

- Added the v1 `learning-event` schema with raw, candidate, and confirmed event kinds.
- Added conservative Python evidence helpers requiring repeated high-confidence evidence before confirmation.
- Split the director into explicit Curriculum, Scaffold, Story World, Assessment, and Learner Model components.
- Persisted director learning events through the local fallback adapter; production deployments can replace the sink with the memory service without changing the wire contract.
- Kept `language_level` and `scaffold_level` independent, including distress level S6.

## Verification

- `npm run typecheck` in `agents/director` passed.
- Contract schema validation is included in `shared/contracts/validate_contracts.py`.
- Physical RX5 validation remains hardware-gated.
