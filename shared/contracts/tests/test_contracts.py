from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1] / "v1"

VALID_CASES = (
    ("learning-turn.schema.json", "learning-turn.json"),
    ("learning-delivery.schema.json", "learning-delivery.json"),
    ("learning-loop.schema.json", "learning-loop.json"),
    ("device-event.schema.json", "device-event.json"),
    ("device-command.schema.json", "device-command.json"),
    ("dashboard-snapshot.schema.json", "dashboard-snapshot.json"),
    ("weekly-report.schema.json", "weekly-report.json"),
    ("parent-constraints.schema.json", "parent-constraints.json"),
    ("device-settings.schema.json", "device-settings.json"),
)

INVALID_CASES = (
    ("learning-turn.schema.json", "learning-turn-mastery.json"),
    ("learning-delivery.schema.json", "learning-delivery-text.json"),
    ("learning-loop.schema.json", "learning-loop-unbounded.json"),
    ("device-event.schema.json", "device-event-missing-version.json"),
    ("device-event.schema.json", "device-event-unknown-type.json"),
    ("device-command.schema.json", "device-command-extra-property.json"),
    ("device-settings.schema.json", "device-settings-volume-out-of-range.json"),
    ("weekly-report.schema.json", "weekly-report-claim-without-evidence.json"),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("schema_name", "fixture_name"), VALID_CASES)
def test_valid_fixtures_match_schema(schema_name: str, fixture_name: str) -> None:
    schema = load_json(ROOT / schema_name)
    payload = load_json(ROOT / "fixtures" / "valid" / fixture_name)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize(("schema_name", "fixture_name"), INVALID_CASES)
def test_invalid_fixtures_are_rejected(schema_name: str, fixture_name: str) -> None:
    schema = load_json(ROOT / schema_name)
    payload = load_json(ROOT / "fixtures" / "invalid" / fixture_name)
    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_contract_version_manifest_is_v1() -> None:
    manifest = load_json(ROOT / "contract-version.json")
    assert manifest == {
        "contract_version": "1.0",
        "json_schema_draft": "2020-12",
    }
