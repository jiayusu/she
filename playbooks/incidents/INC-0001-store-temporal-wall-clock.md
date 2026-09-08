# Incident: store temporal test drifts with the wall clock

## Fingerprint

`test_temporal_filter_excludes_other_days` returned no result for `最近 apple`; the assertion expected day `2026-09-04`.

## Environment

- Windows, Asia/Shanghai, system date 2026-09-07
- Python 3.12 pytest
- Component: `store` — **retired directory, historical path**; succeeded by `backend/memory_store`
- Command at the time: `python -m pytest store/tests -q`
  (today's equivalent: `python -m pytest backend/memory_store/tests -q`)

## Symptoms

Sixty store tests passed and one temporal-window test failed. Re-running from the correct working directory reproduced the same failure.

## Root cause

The fixture anchored episodes and expected windows to `2026-09-04`, while `MemoryService.recall()` called `temporal.parse()` with the live wall clock. The test was date-dependent and expired as the calendar advanced.

## Attempts that did not work

- Changing the shell working directory fixed unrelated engine and Node failures but did not change this assertion.
- No retrieval-ranking change was attempted because tracing showed the date window rejected both candidates before ranking could matter.

## Resolution

Add an optional `now` parameter to `MemoryService.recall()` and pass it to `temporal.parse()`. The test injects its existing `NOW` constant; production callers that omit the parameter retain live-clock behavior.

## Verification

- Before implementation, the focused test failed with `unexpected keyword argument 'now'`.
- After implementation, the focused test passed.
- `python -m pytest store/tests -q` passed all 61 tests (historical path; now `backend/memory_store/tests`).

## Prevention

Tests for relative time must inject a clock or explicit timestamp. Production APIs that parse relative dates should expose a test seam rather than patch global time.

## Skill decision

Keep as incident. The pattern is common, but the repository already uses ordinary dependency injection and one occurrence does not justify a new project skill.
