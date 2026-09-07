# Incident: compressed JSON Schema branch is malformed

## Fingerprint

`json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes` at `device-event.schema.json` line 23.

## Environment

- Windows, Python 3.12
- JSON Schema draft 2020-12 contract authoring
- Command: `python -m pytest A:\working\she\shared\contracts\tests -q`

## Symptoms

Nine contract cases passed; three cases that loaded `device-event.schema.json` failed before schema validation.

## Root cause

Deeply nested `if/then/properties/payload` objects were compressed onto single lines, making closing braces visually ambiguous. One outer `then` object was not closed consistently.

## Attempts that did not work

Adding individual closing braces to dense lines moved the parser error but did not make the structure reliably reviewable.

## Resolution

Expand the `allOf` conditional branches into indented JSON so every object boundary is explicit, then parse with `python -m json.tool` before running semantic contract tests.

## Verification

- `python -m json.tool A:\working\she\shared\contracts\v1\device-event.schema.json` passed.
- Contract suite: 12 passed.
- Standalone validator: 6 valid accepted and 5 invalid rejected.

## Prevention

Do not compress nested conditional JSON Schema branches. Run syntax parsing before semantic validators.

## Skill decision

Keep as incident. Formatting plus automated parsing fully prevents the error; no judgment-heavy skill is required.
