from app.core.logging import redact_sensitive


def test_redacts_sensitive_keys() -> None:
    event = {
        "event": "calling_provider",
        "api_key": "k1",
        "deepgram_api_key": "k2",
        "Authorization": "Token abc",
        "password": "hunter2",
        "refresh_token": "r1",
        "headers": {"ocp-apim-subscription-key": "k3", "accept": "json"},
    }

    result = redact_sensitive(None, "info", event)

    assert result["api_key"] == "[REDACTED]"
    assert result["deepgram_api_key"] == "[REDACTED]"
    assert result["Authorization"] == "[REDACTED]"
    assert result["password"] == "[REDACTED]"
    assert result["refresh_token"] == "[REDACTED]"
    assert result["headers"]["ocp-apim-subscription-key"] == "[REDACTED]"
    assert result["headers"]["accept"] == "json"


def test_keeps_non_secret_fields() -> None:
    event = {"event": "llm_call", "input_tokens": 12, "keyterms": ["cache"], "monkey": "banana"}

    result = redact_sensitive(None, "info", dict(event))

    assert result == event
