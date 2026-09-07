from __future__ import annotations

from typing import Any, Mapping

_IDENTIFIERS = ("event_id", "command_id", "session_id")


def _find_error_code(value: Any) -> str | None:
    if isinstance(value, Mapping):
        code = value.get("error_code")
        if isinstance(code, str):
            return code
        for nested in value.values():
            found = _find_error_code(nested)
            if found:
                return found
    return None


def redact_for_log(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a strict allow-list view suitable for device lifecycle logs."""
    result: dict[str, Any] = {}
    for key in _IDENTIFIERS:
        identifier = value.get(key)
        if isinstance(identifier, str):
            result[key] = identifier[:8]
    event_type = value.get("type")
    if isinstance(event_type, str):
        result["type"] = event_type
    capabilities = value.get("capabilities")
    if isinstance(capabilities, list) and all(isinstance(item, str) for item in capabilities):
        result["capabilities"] = capabilities
    error_code = _find_error_code(value)
    if error_code:
        result["error_code"] = error_code
    return result
