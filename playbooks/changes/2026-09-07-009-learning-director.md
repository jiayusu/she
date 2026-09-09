# Learning-first director endpoint

- Summary: Add a structured `/agent/direct` decision path with separate curriculum, scaffold, story and teaching-action contracts.
- Layer: Backend Service / Agent orchestration
- Contract impact: Extends the route service's internal TypeScript contract; legacy `/agent/dispatch` remains unchanged.
- Historical paths: `route/` was retired after this change and is succeeded by `agents/director/`. The paths below are as-written at the time and do not resolve today.
- Files (historical): `route/src/types.ts`, `route/src/learning-director.ts`, `route/src/app.ts`, `route/src/server.ts`, `route/src/index.ts`, route docs.
- Verification (historical): `Set-Location -LiteralPath './route'; npm run typecheck`; existing route suite (`npm test`) remains green. Today's equivalent runs in `agents/director`.
- Rollback: Remove the `/agent/direct` route and `learning-director.ts`; legacy dispatch is independent.
- Reusable knowledge: Keep `language_level` and `scaffold_level` distinct. Emotion distress forces a pause and candidate-only memory policy. Conflict-marker audits must match exact Git markers so documentation separators are not false positives.
- Commit binding: same commit as this record
