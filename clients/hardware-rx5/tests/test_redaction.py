from she_device.redaction import redact_for_log


def test_sensitive_fields_are_removed_recursively():
    payload = {
        "event_id": "11111111-1111-4111-8111-111111111111",
        "type": "pointing",
        "utterance": "I want milk",
        "audio": "base64-secret",
        "image": "base64-secret",
        "token": "secret-token",
        "payload": {"error_code": "camera_unavailable", "text": "private"},
        "capabilities": ["short_capture"],
    }

    assert redact_for_log(payload) == {
        "event_id": "11111111",
        "type": "pointing",
        "capabilities": ["short_capture"],
        "error_code": "camera_unavailable",
    }


def test_unknown_fields_are_not_preserved():
    assert redact_for_log({"child_name": "private", "debug": "private"}) == {}
