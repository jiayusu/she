# Incident: Assessment was aligned with the next target

## Fingerprint

A milk task followed by a correct milk reply and a new apple context was evaluated
against apple. First contact could also be scored against a task never returned before.
The regression suite observed 5 new failing cases, while the previous 66 tests passed.

## Environment

Director direct endpoint, Node 20, TypeScript. All inputs in new tests are synthetic.

## Symptoms

Wrong target/support attribution, unbounded repeated prompting, and low-confidence
input treated as a learning attempt.

## Root cause

Curriculum and Scaffold were calculated before Assessment, and their new values were
passed as the assessment target/support. There was no bounded prior-turn context.

## Attempts that did not work

None for the runtime resolution. During test authoring, an HTTP JSON value needed an
explicit response type to satisfy strict TypeScript; corrected before final checks.

## Resolution

Store only bounded in-memory preceding action context. Assess before next planning;
skip assessment for first/uncertain/listening/emotion-paused inputs. Count at most two
unsuccessful replies, then pause until clear voluntary input. Do not use the old raw
JSONL fallback as a Shared State writer for the new endpoint.

## Verification

`npm test --prefix agents/director`: 76 passed. `npm run typecheck --prefix agents/director`:
passed. `python -m pytest shared/contracts/tests -q`: 14 passed. Tests cover HTTP entry,
no raw learning file creation, unchanged learner state, lifecycle order, session isolation,
expiry/capacity and pause recovery.

## Prevention

Keep target attribution, finite lifecycle and candidate-only policy in regression tests.
Track future ACK/idempotency work separately; preceding planned output is not proof of
actual device execution.

## Skill decision

Keep as incident: automatic regression tests are more appropriate than a workflow skill.
