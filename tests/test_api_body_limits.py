"""Regression coverage for bounded HTTP ingest payloads."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


def test_invalid_body_limit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("0", "-1", "abc", "16777217"):
        monkeypatch.setenv("LOGSIGHT_API_MAX_BODY_BYTES", value)
        with pytest.raises(RuntimeError, match="LOGSIGHT_API_MAX_BODY_BYTES"):
            api.create_app()


def test_oversized_single_and_batch_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setenv("LOGSIGHT_API_MAX_BODY_BYTES", "128")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    api._recent.clear()
    with TestClient(api.create_app()) as client:
        for path in ("/v1/logs", "/v1/logs/batch"):
            payload = {"logs": [{"line": "INFO " + "x" * 256}]}
            if path == "/v1/logs":
                payload = {"line": "INFO " + "x" * 256}
            response = client.post(path, json=payload)
            assert response.status_code == 413
            assert response.json() == {"detail": "Request body too large"}
        assert client.get("/health").status_code == 200
        assert client.get("/v1/logs/recent").json()["count"] == 0
        response = client.post("/v1/logs", json={"line": "INFO accepted"})
        assert response.status_code == 200
    api._recent.clear()


@pytest.mark.anyio
async def test_streamed_body_over_limit_is_rejected() -> None:
    """ASGI clients may stream without a Content-Length header."""
    from logsight.request_limits import IngestionBodyLimit

    reached_app = False

    async def inner(scope, receive, send):
        nonlocal reached_app
        reached_app = True

    wrapper = IngestionBodyLimit(inner, max_body_bytes=5)
    incoming = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )
    output = []

    async def receive():
        return next(incoming)

    async def send(message):
        output.append(message)

    await wrapper(
        {"type": "http", "method": "POST", "path": "/v1/logs", "headers": []},
        receive,
        send,
    )
    assert reached_app is False
    assert output[0]["status"] == 413
