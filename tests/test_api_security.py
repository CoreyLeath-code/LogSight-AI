"""Security-boundary tests for the optional FastAPI gateway."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight.api import create_app


def test_token_mode_rejects_missing_or_short_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "token")
    monkeypatch.delenv("LOGSIGHT_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="at least 32"):
        create_app()

    monkeypatch.setenv("LOGSIGHT_API_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        create_app()


def test_invalid_auth_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "unknown")
    with pytest.raises(RuntimeError, match="disabled or token"):
        create_app()


def test_authenticated_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "a" * 48
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "token")
    monkeypatch.setenv("LOGSIGHT_API_TOKEN", token)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        for path in ("/metrics", "/v1/logs/recent"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert response.headers["cache-control"] == "no-store"
            assert client.get(path, headers={"Authorization": "Basic abc"}).status_code == 401
            assert client.get(
                path, headers={"Authorization": "Bearer " + "b" * 48}
            ).status_code == 401
            assert client.get(
                path, headers={"Authorization": f"Bearer {token}"}
            ).status_code == 200

        payload = {"line": "INFO demonstration", "service": "api"}
        assert client.post("/v1/logs", json=payload).status_code == 401
        assert client.post("/v1/logs/batch", json={"logs": [payload]}).status_code == 401


def test_local_mode_retains_backwards_compatibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.delenv("LOGSIGHT_API_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/metrics").status_code == 200
        assert client.get("/v1/logs/recent").status_code == 200
