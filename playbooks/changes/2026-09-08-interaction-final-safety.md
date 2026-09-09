# Change: Validate Interaction fallback text after slot rendering

**Commit binding:** Same commit as this record.

## Layer

Agent output orchestration at the Trust Boundary. Existing safety rules and
Assessment logic are unchanged; Engine now invokes the existing filters on its
rendered fallback output.

## Fingerprint

`test_final_fallback_rejects_unsafe_assessment_slot` fails because an untrusted,
synthetic assessment slot survives in the final text after the original output
has been rejected. The same leak occurs after unavailable or malformed model
responses and with a configured pass-through adapter.

## Environment

Windows, Python 3.12.9, `agents/interaction`; tests use in-memory synthetic inputs
and offline provider doubles. No model service, child recording or hardware is used.

## Symptoms

The original output is filtered and a nonempty fallback is returned, but rendering
an unchecked slot into that fallback can reintroduce content rejected by the
existing LocalSafetyFilter.

## Root cause

`Engine._safe_or_template` checked the initial response, then returned a newly
rendered dynamic template without checking it. Provider-failure and silence paths
also converge on this method. A custom adapter could additionally omit the local
safety floor.

## Attempts that did not work

None. Regression tests demonstrated the missing check before implementation.

## Resolution

- Apply the existing LocalSafetyFilter after the configured adapter accepts text.
- Filter fully rendered fallback text through the configured adapter and the local
  filter; rejected fallback text becomes a fixed, reviewed greeting without slots.
- Report `template_id=hardcoded` and `template_hit=false` when the dynamic fallback
  is rejected. Preserve the nonempty response guarantee.
- Custom safety adapters may impose additional restrictions, but cannot disable
  the local text safety floor. A rejecting adapter still reaches the fixed greeting.

## Files and contract impact

`agents/interaction/src/she_engine/engine.py` and
`agents/interaction/tests/test_engine_e2e.py`. No shared contract or RPG document
changes. Existing fallback metadata fields are reused.

## Verification

Run from `agents/interaction`:

```sh
python -m pytest tests/test_engine_e2e.py -k final_fallback -q -p no:cacheprovider
python -m pytest tests -q -p no:cacheprovider
```

Before implementation: the three provider-path regressions failed on the unsafe
final text; adding default/custom-adapter coverage produced six expected failures.
After implementation: all six regressions pass and the complete 110-test
Interaction suite passes. `git diff --check` passes (Windows line-ending notices
are informational).

## Prevention

The regression matrix covers model text rejection, model unavailability and
malformed output, each with the default and a pass-through adapter. Assertions
check the real Engine final text, nonempty fallback and hardcoded-fallback metadata.

## Rollback

Revert the Engine, regression test and this record together only if replacing the
fix with another verified final-output safety guard; reverting alone restores the
documented leak.

## Skill decision

Keep as incident-shaped change evidence using `playbooks/templates/incident.md`.
The stable guard belongs in automated regression tests rather than a new skill.
