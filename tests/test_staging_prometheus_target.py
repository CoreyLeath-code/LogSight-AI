"""Tests exercise mocked Prometheus API responses without network access."""

from __future__ import annotations

import json

import pytest

from scripts import staging_prometheus_target as target


def payload() -> dict[str, object]:
    return {
        "status": "success",
        "data": {
            "activeTargets": [
                {
                    "labels": {"job": "logsight-staging", "instance": "logsight-api:8000"},
                    "scrapeUrl": "http://logsight-api:8000/metrics",
                    "health": "up",
                    "lastScrape": "2026-11-22T22:00:00Z",
                    "lastError": "",
                }
            ]
        },
    }


def test_observed_healthy_target_passes() -> None:
    result = target.assess_prometheus_target(payload(), "logsight-staging", "logsight-api:8000")
    assert result["status"] == "pass"
    assert result["independent_service_sli_verified"] is False


@pytest.mark.parametrize("changed", ["down", "error", "bad_path", "no_scrape"])
def test_unhealthy_or_invalid_target(changed: str) -> None:
    data = payload()
    obj = data["data"]["activeTargets"][0]
    if changed == "down":
        obj["health"] = "down"
    elif changed == "error":
        obj["lastError"] = "scrape failed"
    elif changed == "bad_path":
        obj["scrapeUrl"] = "http://logsight-api:8000/health"
    else:
        obj["lastScrape"] = ""
    if changed in {"bad_path", "no_scrape"}:
        with pytest.raises(ValueError):
            target.assess_prometheus_target(data, "logsight-staging", "logsight-api:8000")
    else:
        assert (
            target.assess_prometheus_target(data, "logsight-staging", "logsight-api:8000")["status"]
            == "fail"
        )


def test_missing_and_duplicate_targets_rejected() -> None:
    data = payload()
    with pytest.raises(ValueError, match="exactly one"):
        target.assess_prometheus_target(data, "different", "logsight-api:8000")
    data["data"]["activeTargets"].append(data["data"]["activeTargets"][0])
    with pytest.raises(ValueError, match="exactly one"):
        target.assess_prometheus_target(data, "logsight-staging", "logsight-api:8000")


@pytest.mark.parametrize(
    "url",
    [
        "http://prometheus.example",
        "https://user:pass@prometheus.example",
        "https://prometheus.example/api/v1/targets",
        "https://prometheus.example?token=secret",
        "file:///tmp/targets",
    ],
)
def test_rejects_unsafe_api_urls(url: str) -> None:
    with pytest.raises(ValueError):
        target.validate_prometheus_url(url)


def test_staging_api_requires_token_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("must not open network")

    monkeypatch.setattr(target, "build_opener", forbidden)
    with pytest.raises(ValueError, match="PROMETHEUS_STAGING_TOKEN"):
        target.observe_target("https://prometheus.example", "", "job", "instance")


def test_staging_api_uses_only_target_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == 1024 * 1024 + 1
            return json.dumps(payload()).encode()

    class Opener:
        def open(self, req: object, timeout: int) -> Response:
            assert req.full_url == "https://prometheus.example/api/v1/targets?state=active"
            assert req.get_header("Authorization") == "Bearer synthetic-secret"
            assert timeout == 8
            return Response()

    monkeypatch.setattr(target, "build_opener", lambda *args: Opener())
    result = target.observe_target(
        "https://prometheus.example",
        "synthetic-secret",
        "logsight-staging",
        "logsight-api:8000",
    )
    assert result["status"] == "pass"


def test_redirect_handler_refuses_forwarding() -> None:
    from urllib.request import Request

    req = Request(
        "https://prometheus.example/api/v1/targets",
        headers={"Authorization": "Bearer synthetic-secret"},
    )
    assert (
        target._NoRedirect().redirect_request(
            req, None, 302, "redirect", {}, "https://other.example/targets"
        )
        is None
    )
