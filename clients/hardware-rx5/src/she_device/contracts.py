from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

CONTRACT_VERSION = "1.0"


class ContractError(ValueError):
    """Raised when a gateway message does not match the checked-in contract."""


def _contract_root() -> Path:
    configured = os.environ.get("SHE_CONTRACT_ROOT")
    if configured:
        return Path(configured)
    repository_root = Path(__file__).resolve().parents[4]
    repository_contracts = repository_root / "shared" / "contracts" / "v1"
    if repository_contracts.is_dir():
        return repository_contracts
    return Path("/opt/she/shared/contracts/v1")


def _validate(schema_name: str, payload: Mapping[str, Any]) -> None:
    schema_path = _contract_root() / schema_name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"contract_schema_unavailable:{schema_name}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        raise ContractError("contract_invalid:" + errors[0].message)


@dataclass(frozen=True, slots=True)
class DeviceCommand:
    command_id: str
    contract_version: str
    device_id: str
    session_id: str
    sequence: int
    issued_at: str
    expires_at: str
    type: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DeviceCommand":
        materialized = dict(value)
        _validate("device-command.schema.json", materialized)
        return cls(
            command_id=str(materialized["command_id"]),
            contract_version=str(materialized["contract_version"]),
            device_id=str(materialized["device_id"]),
            session_id=str(materialized["session_id"]),
            sequence=int(materialized["sequence"]),
            issued_at=str(materialized["issued_at"]),
            expires_at=str(materialized["expires_at"]),
            type=str(materialized["type"]),
            payload=dict(materialized["payload"]),
        )


def validate_event(value: Mapping[str, Any]) -> dict[str, Any]:
    materialized = dict(value)
    _validate("device-event.schema.json", materialized)
    return materialized
