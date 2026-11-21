"""Inference enqueue failures return safe, explicit ambiguous-delivery responses."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from logsight import api


class BrokenDispatcher:
    def submit_embeddings(self, events: object) -> str:
        raise ConnectionError("secret-broker-password")


def test_inference_failure_is_sanitized_and_reports_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", BrokenDispatcher())
    with TestClient(api.create_app()) as client:
        response = client.post(
            "/v1/logs",
            json={
                "line": "ERROR payment service unavailable",
                "service": "payments",
                "source": "test",
                "host": "test-host",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"] == (
            "Inference queue acknowledgement not confirmed; retry may duplicate event"
        )
        assert "secret-broker-password" not in response.text


def test_local_mode_ingestion_without_inference_queue_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGSIGHT_API_KAFKA_ENABLED", "false")
    monkeypatch.setenv("LOGSIGHT_API_AUTH_MODE", "disabled")
    monkeypatch.setattr(api, "_admission_controller", None)
    monkeypatch.setattr(api, "_inference_dispatcher", None)
    with TestClient(api.create_app()) as client:
        response = client.post(
            "/v1/logs",
            json={
                "line": "INFO service started",
                "service": "test",
                "source": "test",
                "host": "test-host",
            },
        )
        assert response.status_code == 200
        assert "inference_task_id" not in response.json()
