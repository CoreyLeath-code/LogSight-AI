"""Regression tests for the API log-input redaction foundation."""

from __future__ import annotations

import pytest

from logsight.redaction import redact_log_line


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("ERROR password=supersecret failed", "supersecret"),
        ("INFO api_key: abc123 request", "abc123"),
        ("WARN access_token='sensitive value' expired", "sensitive value"),
        ("INFO Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
        ("ERROR contact person@example.org", "person@example.org"),
    ],
)
def test_sensitive_strings_removed(raw: str, secret: str) -> None:
    safe = redact_log_line(raw)
    assert secret not in safe
    assert "[REDACTED]" in safe


def test_unrelated_log_structure_preserved() -> None:
    original = "2026-11-19T10:00:00Z ERROR disk space low"
    assert redact_log_line(original) == original


def test_api_redacts_before_return_and_recent_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from logsight import api

    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    monkeypatch.setattr(api, "_template_parser", api.build_template_parser())
    api._recent.clear()
    with TestClient(api.create_app()) as client:
        response = client.post(
            "/v1/logs",
            json={"line": "ERROR password=topsecret contact user@example.com"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "topsecret" not in str(body)
        assert "user@example.com" not in str(body)
        recent = client.get("/v1/logs/recent")
        assert recent.status_code == 200
        assert "topsecret" not in recent.text
        assert "user@example.com" not in recent.text
    api._recent.clear()
