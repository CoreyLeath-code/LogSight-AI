"""Alertmanager tests use mock responses; CI never sends or receives alerts."""

from __future__ import annotations

import json

import pytest

from scripts import staging_alertmanager_routing as route


def response() -> list[dict[str, object]]:
    return [
        {
            "labels": {"alertname": "LogSightAPIMetricsScrapeMissing"},
            "status": {"state": "active"},
            "receivers": [{"name": "staging-oncall"}],
        }
    ]


def test_active_alert_with_expected_receiver_passes() -> None:
    report = route.assess_alertmanager_routing(
        response(), "LogSightAPIMetricsScrapeMissing", "staging-oncall"
    )
    assert report["status"] == "pass"
    assert report["receiver_delivery_verified"] is False
    assert report["human_acknowledgment_verified"] is False


@pytest.mark.parametrize("failure", ["silenced", "wrong_receiver"])
def test_unrouted_or_suppressed_alert_fails(failure: str) -> None:
    data = response()
    if failure == "silenced":
        data[0]["status"]["state"] = "suppressed"
    else:
        data[0]["receivers"] = [{"name": "other"}]
    assert (
        route.assess_alertmanager_routing(
            data, "LogSightAPIMetricsScrapeMissing", "staging-oncall"
        )["status"]
        == "fail"
    )


@pytest.mark.parametrize("problem", ["none", "duplicate", "missing_status", "missing_receivers"])
def test_incomplete_alert_data_rejected(problem: str) -> None:
    data = response()
    if problem == "none":
        data.clear()
    elif problem == "duplicate":
        data.append(data[0])
    elif problem == "missing_status":
        del data[0]["status"]
    else:
        del data[0]["receivers"]
    with pytest.raises(ValueError):
        route.assess_alertmanager_routing(data, "LogSightAPIMetricsScrapeMissing", "staging-oncall")


def test_requires_bearer_token_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(route, "build_opener", forbidden)
    with pytest.raises(ValueError, match="ALERTMANAGER_STAGING_TOKEN"):
        route.observe_alertmanager("https://alertmanager.example", "", "TestAlert", "staging")


def test_reads_only_alertmanager_alerts_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == 1024 * 1024 + 1
            return json.dumps(response()).encode()

    class Opener:
        def open(self, request: object, timeout: int) -> Response:
            assert request.full_url == "https://alertmanager.example/api/v2/alerts"
            assert request.get_header("Authorization") == "Bearer synthetic-secret"
            assert timeout == 8
            return Response()

    monkeypatch.setattr(route, "build_opener", lambda *args: Opener())
    report = route.observe_alertmanager(
        "https://alertmanager.example",
        "synthetic-secret",
        "LogSightAPIMetricsScrapeMissing",
        "staging-oncall",
    )
    assert report["status"] == "pass"


def test_rejects_insecure_nonloopback_url() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        route.observe_alertmanager("http://alertmanager.example", "secret", "Alert", "r")


def test_invalid_json_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return b"{"

    class Opener:
        def open(self, request: object, timeout: int) -> Response:
            return Response()

    monkeypatch.setattr(route, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="valid JSON"):
        route.observe_alertmanager("https://example.test", "secret", "Alert", "receiver")
