from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parent / "v1"
VALID = {
    "learning-loop.json": "learning-loop.schema.json",
    "device-event.json": "device-event.schema.json",
    "device-command.json": "device-command.schema.json",
    "dashboard-snapshot.json": "dashboard-snapshot.schema.json",
    "weekly-report.json": "weekly-report.schema.json",
    "parent-constraints.json": "parent-constraints.schema.json",
    "device-settings.json": "device-settings.schema.json",
}
INVALID = {
    "learning-loop-unbounded.json": "learning-loop.schema.json",
    "device-event-missing-version.json": "device-event.schema.json",
    "device-event-unknown-type.json": "device-event.schema.json",
    "device-command-extra-property.json": "device-command.schema.json",
    "device-settings-volume-out-of-range.json": "device-settings.schema.json",
    "weekly-report-claim-without-evidence.json": "weekly-report.schema.json",
}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    failures: list[str] = []
    schemas = {name: Draft202012Validator(read(ROOT / name)) for name in set(VALID.values()) | set(INVALID.values())}
    learning_schema = read(ROOT / "learning-event.schema.json")
    Draft202012Validator.check_schema(learning_schema)

    for fixture, schema in VALID.items():
        errors = list(schemas[schema].iter_errors(read(ROOT / "fixtures" / "valid" / fixture)))
        if errors:
            failures.append(f"valid/{fixture}: {errors[0].message}")

    for fixture, schema in INVALID.items():
        errors = list(schemas[schema].iter_errors(read(ROOT / "fixtures" / "invalid" / fixture)))
        if not errors:
            failures.append(f"invalid/{fixture}: unexpectedly accepted")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print(f"Contracts OK: {len(VALID)} valid accepted, {len(INVALID)} invalid rejected, version 1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
