"""No network or alerts are sent by tests: all API calls are mocked."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts import staging_synthetic_alert_drill as drill


def specimen() -> dict[str, object]:
    return drill.make_drill(
        "staging-drill-123", "CHANGE-1234", datetime(2026, 11, 22, tzinfo=timezone.utc)
    )


def test_synthetic_alert_is_bounded_and_contains_no_sensitive_event() -> None:
    example = specimen()
    assert example["labels"]["alertname"] == "LogSightStagingSyntheticDeliveryDrill"
    assert example["labels"]["environment"] == "staging"
    assert example["startsAt"] == "2026-11-22T00:00:00Z"
    assert example["endsAt"] == "2026-11-22T00:05:00Z"
    assert "payload" not in json.dumps(example)


@pytest.mark.parametrize(
    ("identity", "ticket"),
    [("BAD", "CHANGE-1234"), ("staging-drill-123", "bad ticket")],
)
def test_invalid_drill_identity_rejected(identity: str, ticket: str) -> None:
    with pytest.raises(ValueError):
        drill.make_drill(identity, ticket, datetime.now(timezone.utc))


@pytest.mark.parametrize(
    "url",
    [
        "https://alertmanager.example",
        "http://alertmanager-staging.example",
        "https://user:pass@alertmanager-staging.example",
        "https://alertmanager-staging.example/api/v2/alerts",
    ],
)
def test_wrong_or_insecure_endpoint_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        drill.check_staging_endpoint(url)


def test_dry_run_never_opens_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("unexpected network")

    monkeypatch.setattr(drill, "build_opener", forbidden)
    result = drill.submit_drill(
        "https://alertmanager-staging.example",
        "",
        specimen(),
        "CHANGE-1234",
        "",
        False,
        "",
    )
    assert result["status"] == "dry_run"
    assert result["receiver_delivery_verified"] is False


@pytest.mark.parametrize(
    ("env_ticket", "confirm", "token"),
    [
        ("", "SEND_SYNTHETIC_STAGING_ALERT", "synthetic"),
        ("CHANGE-OTHER", "SEND_SYNTHETIC_STAGING_ALERT", "synthetic"),
        ("CHANGE-1234", "", "synthetic"),
        ("CHANGE-1234", "SEND_SYNTHETIC_STAGING_ALERT", ""),
    ],
)
def test_execution_fails_closed_without_all_gates(
    monkeypatch: pytest.MonkeyPatch, env_ticket: str, confirm: str, token: str
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("unexpected network")

    monkeypatch.setattr(drill, "build_opener", forbidden)
    with pytest.raises(ValueError):
        drill.submit_drill(
            "https://alertmanager-staging.example",
            token,
            specimen(),
            "CHANGE-1234",
            env_ticket,
            True,
            confirm,
        )


def test_explicit_execution_posts_only_synthetic_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class Response:
        status = 202

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    class Opener:
        def open(self, request: object, timeout: int) -> Response:
            calls.append(request)
            assert timeout == 8
            return Response()

    monkeypatch.setattr(drill, "build_opener", lambda *args: Opener())
    result = drill.submit_drill(
        "https://alertmanager-staging.example",
        "synthetic-secret",
        specimen(),
        "CHANGE-1234",
        "CHANGE-1234",
        True,
        "SEND_SYNTHETIC_STAGING_ALERT",
    )
    assert result["status"] == "submitted_not_delivered"
    assert result["receiver_delivery_verified"] is False
    request = calls[0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://alertmanager-staging.example/api/v2/alerts"
    assert request.get_header("Authorization") == "Bearer synthetic-secret"
    payload = json.loads(request.data)
    assert len(payload) == 1
    assert payload[0]["labels"]["environment"] == "staging"
