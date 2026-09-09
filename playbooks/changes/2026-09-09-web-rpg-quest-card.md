# Change: add the parent Web read-only RPG quest card

**Commit binding:** Same commit as this record.

## Layer

Web.

## Summary

Add an optional parent-facing projection of the current `milk_picnic.v1`
quest:

- `LiveAppApi.questState(childId, sessionId)` reads only Gateway
  `GET /v1/rpg/state` and URL-encodes both identity values;
- the Web decoder rejects missing, additional, unknown, and node-incompatible
  fields against the finite `rpg-quest-summary` model;
- `AppModel` requests the summary only when both demo identity values are
  explicitly supplied;
- the Today page shows phase, reviewed world role, target expression, virtual
  inventory, next quest, and delivery status in a read-only card;
- RPG read failure is isolated from the existing dashboard so an optional demo
  integration cannot replace already available parent content with an offline
  page.

The browser receives no world/mastery write method and contains no node
transition, Speech Act, assessment, or scaffold logic. The card does not show a
child utterance, evidence, raw perception, debug prompt, or complete Memory
response.

Production identity remains unimplemented. The entry point only enables the
demo read when both `VITE_SHE_RPG_CHILD_ID` and
`VITE_SHE_RPG_SESSION_ID` are non-blank; a partial or absent configuration
causes no RPG request and no card.

## Contract impact

No shared contract change. Web now consumes the existing
`shared/contracts/v1/rpg-quest-summary.schema.json` response and exposes no new
write contract.

## Files

- `clients/web/src/api/contracts.ts`
- `clients/web/src/api/appApi.ts`
- `clients/web/src/state/appModel.ts`
- `clients/web/src/main.tsx`
- `clients/web/src/features/TodayView.tsx`
- `clients/web/src/design/theme.css`
- `clients/web/tests/contractDecoding.test.ts`
- `clients/web/tests/liveAppApi.test.ts`
- `clients/web/tests/appModel.test.ts`
- `clients/web/tests/parentExperience.test.tsx`
- `clients/web/README.md`
- `playbooks/changes/2026-09-09-web-rpg-quest-card.md`

## Verification

Not run, following the user's explicit instruction to edit files without
running tests, typechecks, builds, lint, audit scripts, or other verification
commands. Test source was added for the decoder, URL construction, opt-in model
loading, isolated quest failure, and Today card rendering; all results remain
pending.
