"""Staging preflight is validated offline; no remote requests in CI."""

from __future__ import annotations

from urllib.request import Request

import pytest

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
        redirect.redirect_request(req, None, 302, "redirect", {}, "https://other.example/metrics")
        is None
    )


def test_get_reads_authorized_metric_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from logsight import staging_scrape_preflight as preflight

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            assert size == 128 * 1024
            return b"logsight_readiness_success_total 1"

    class Opener:
        def open(self, request: Request, timeout: int) -> Response:
            assert request.get_header("Authorization") == "Bearer synthetic-token"
            assert timeout == 5
            return Response()

    monkeypatch.setattr(preflight, "build_opener", lambda *args: Opener())
    assert preflight._get("https://logsight.example/metrics", "synthetic-token") == (
        200,
        "logsight_readiness_success_total 1",
    )


def test_get_rejects_network_failure_and_handles_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from urllib.error import HTTPError, URLError

    from logsight import staging_scrape_preflight as preflight

    class Opener:
        error: Exception = HTTPError("https://logsight.example/metrics", 401, "No", {}, None)

        def open(self, request: Request, timeout: int) -> None:
            raise self.error

    opener = Opener()
    monkeypatch.setattr(preflight, "build_opener", lambda *args: opener)
    assert preflight._get("https://logsight.example/metrics") == (401, "")
    opener.error = URLError("synthetic connection failure")
    with pytest.raises(ValueError, match="target request failed"):
        preflight._get("https://logsight.example/metrics")


def test_preflight_main_exit_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from logsight import staging_scrape_preflight as preflight

    monkeypatch.setenv("LOGSIGHT_STAGING_SCRAPE_TOKEN", "a" * 32)
    monkeypatch.setattr(
        sys,
        "argv",
        ["preflight", "--base-url", "https://logsight.example"],
    )
    monkeypatch.setattr(
        preflight,
        "run_preflight",
        lambda base, token: {"health_ok": True, "metrics_authenticated": True},
    )
    assert preflight.main() == 0
    assert "health_ok: pass" in capsys.readouterr().out
    monkeypatch.setattr(
        preflight,
        "run_preflight",
        lambda base, token: {"metrics_authenticated": False},
    )
    assert preflight.main() == 1
    assert "metrics_authenticated: fail" in capsys.readouterr().out

    def invalid(base: str, token: str) -> dict[str, bool]:
        raise ValueError("synthetic invalid configuration")

    monkeypatch.setattr(preflight, "run_preflight", invalid)
    with pytest.raises(SystemExit) as error:
        preflight.main()
    assert error.value.code == 2
