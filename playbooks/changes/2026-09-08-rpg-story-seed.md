# Change: Add the finite milk picnic story asset and strict loader

**Commit binding:** Same commit as this record.

## Layer

Agent content and deterministic asset validation. No Director runtime, Shared State,
device control, Assessment or safety-rule changes.

## Summary

Add `agents/director/content/story-seeds/milk_picnic.v1.json` with the approved
product sequence `collect_milk -> find_red_cup -> picnic_ready`. The first node
requires a fridge, requests milk and grants a virtual milk token. The second
requires the table plus red/blue cup observations, selects the red cup and grants
a virtual red-cup token. The terminal node completes the pretend picnic.

Each node includes its world role, motivation, learning goal, target expression,
criterion, S0-S6 prompt IDs, success/failure feedback IDs and permitted next event.
Terminal nodes have no Speech Act criterion, object requirement or successor.
The asset declares allowed events, virtual items and language levels at the top.

## Public API and invariants

`agents/director/src/story-seed.ts` exports `loadStorySeed(path?)` and
`validateStorySeed(unknown)`, returning the discriminated `StorySeed`/`StoryNode`
types. The default asset path is relative to the module, independent of shell cwd.

- Every object level has an exact required-field list; unknown fields are rejected.
- Identifiers, nonempty text, arrays, integer versions and levels are bounded.
- Node and prompt IDs are unique across the seed; criterion IDs are also unique.
- Every node has one prompt for each S0-S6 level. Prompt IDs reference future
  Interaction content; this loader does not claim those renderer assets exist.
- `accepted_forms[].requires_prompt_id=null` denotes a context-independent form;
  a non-null value must reference a prompt in the same node.
- Nonterminal events must grant a declared virtual item; the terminal event must
  complete this seed. Only declared event kinds can be emitted.
- Every node must be reachable from the start; successors must exist; the finite
  single-successor graph must terminate at the unique declared completion node.
- Invalid content throws `invalid_story_seed:<location>:<reason>` without echoing
  untrusted content. There is no execution of code, templates or model calls.

## Files and contract impact

New asset, loader and `agents/director/test/story-seed.test.ts`. No existing
Director types or runtime files were changed. These are local content types;
future cross-component RPG traffic must use the separately defined shared
contracts. This stage does not yet load the asset in LearningDirector.

## Verification

Run from `agents/director`:

```sh
node --import tsx --test --test-name-pattern=rejects test/story-seed.test.ts
node --import tsx --test test/story-seed.test.ts
npm test
npm run typecheck
```

TDD evidence: first the test module exposed the missing loader. After an API-only
identity scaffold made the suite executable, all 39 rejection cases failed with
`Missing expected exception`; strict validation was implemented only afterwards.
The final targeted suite passes 41 tests, including real asset loading. The full
Director suite passes 118 tests; TypeScript and `git diff --check` pass.

## Rollback

Revert the three new Director files and this record together. No runtime state or
schema migration is needed because the loader is not yet wired into live planning.

## Reusable knowledge

Keep asset shape and graph checks executable. Human content review and checking
that Interaction provides every referenced prompt remain separate integration
requirements; passing static validation alone does not establish learning efficacy.
