"""Staging preflight is validated offline; no remote requests in CI."""

from __future__ import annotations

import pytest

from urllib.request import Request

from logsight.staging_scrape_preflight import _RejectRedirect, run_preflight, validate_target


@pytest.mark.parametrize(
    "url",
    [
        "http://logsight.example",
        "http://user:password@127.0.0.1:8000",
        "https://example.test/metrics",
        "https://example.test?token=secret",
        "file:///tmp/test",
    ],
)
def test_preflight_rejects_unsafe_target_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_target(url)


def test_preflight_allows_https_and_loopback_only() -> None:
    assert validate_target("https://logsight.example/") == "https://logsight.example"
    assert validate_target("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_preflight_requires_token_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(url: str, token: str | None = None) -> tuple[int, str]:
        raise AssertionError("should not make request")

    monkeypatch.setattr("logsight.staging_scrape_preflight._get", forbidden)
    with pytest.raises(ValueError, match="at least 32"):
        run_preflight("https://logsight.example", "short")


def test_preflight_requires_all_four_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_get(url: str, token: str | None = None) -> tuple[int, str]:
        calls.append((url, token is not None))
        if url.endswith("/health"):
            return 200, "ok"
        if url.endswith("/ready"):
            return 200, "ready"
        if token is None:
            return 401, ""
        return 200, "logsight_readiness_success_total 1"

    monkeypatch.setattr("logsight.staging_scrape_preflight._get", fake_get)
    checks = run_preflight("https://logsight.example", "a" * 32)
    assert all(checks.values())
    assert len(calls) == 4
    assert calls[-2:] == [
        ("https://logsight.example/metrics", False),
        ("https://logsight.example/metrics", True),
    ]


def test_preflight_fails_closed_if_metrics_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(url: str, token: str | None = None) -> tuple[int, str]:
        return 200, "logsight_readiness_success_total 1"

    monkeypatch.setattr("logsight.staging_scrape_preflight._get", fake_get)
    assert (
        run_preflight("https://logsight.example", "a" * 32)["metrics_unauthorized_without_token"]
        is False
    )


def test_redirect_handler_rejects_cross_target_token_forwarding() -> None:
    req = Request(
        "https://logsight.example/metrics",
        headers={"Authorization": "Bearer synthetic-secret"},
    )
    redirect = _RejectRedirect()
    assert (
        redirect.redirect_request(
            req, None, 302, "redirect", {}, "https://other.example/metrics"
        )
        is None
    )
