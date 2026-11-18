import json

from shared.security.pii import anonymize_data


def test_nested_email_anonymization():
    data = {
        "ok": True,
        "result": {
            "email": "test@example.com",
            "status": "ACTIVE",
        },
    }

    result = anonymize_data(data)

    assert "test@example.com" not in json.dumps(result)
    assert result["result"]["status"] == "ACTIVE"
    assert result["ok"] is True


def test_nested_phone_anonymization():
    data = {
        "notifications": [
            {"phone": "+380671234567"},
            {"phone": "0671234567"},
        ],
    }

    result = anonymize_data(data)

    serialized = json.dumps(result)

    assert "+380671234567" not in serialized
    assert "0671234567" not in serialized


def test_uuid_preservation():
    loan_id = "550e8400-e29b-41d4-a716-446655440000"

    data = {
        "loan_id": loan_id,
        "notification_received": True,
    }

    result = anonymize_data(data)

    assert result["loan_id"] == loan_id
    assert result["notification_received"] is True


def test_json_structure_preservation():
    data = {
        "skill": "issue_loan",
        "event_queued": True,
        "result": {
            "email": "test@example.com",
            "count": 5,
            "items": ["book1", "book2"],
        },
    }

    result = anonymize_data(data)

    encoded = json.dumps(result)
    decoded = json.loads(encoded)

    assert decoded["skill"] == "issue_loan"
    assert decoded["event_queued"] is True
    assert decoded["result"]["count"] == 5
    assert len(decoded["result"]["items"]) == 2
    assert "test@example.com" not in encoded


def test_original_data_not_mutated():
    data = {"email": "test@example.com"}

    result = anonymize_data(data)

    assert data["email"] == "test@example.com"
    assert result["email"] != data["email"]
