"""ClickHouse HTTPS, credential, and CA verification contracts."""

from __future__ import annotations

import ssl
import urllib.request
from typing import Any

import pytest

from logsight.storage import ClickHouseStore


@pytest.mark.parametrize(
    "url",
    [
        "ftp://clickhouse:8123",
        "https://user:password@clickhouse.example:8443",
        "https://clickhouse.example:8443/?query=secret",
        "https://clickhouse.example:8443/#fragment",
        "https://clickhouse.example:8443/internal",
        "https://",
    ],
)
def test_invalid_or_embedded_secret_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        ClickHouseStore(base_url=url)


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "test"},
        {"password": "test"},
        {"username": "test", "password": "test"},
        {"ca_file": "/path/to/ca.pem"},
    ],
)
def test_insecure_or_partial_configuration_fails_closed(credentials: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        ClickHouseStore(base_url="http://clickhouse:8123", **credentials)


def test_valid_https_client_checks_hostname_and_sends_credentials_only_in_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[urllib.request.Request, dict[str, Any]]] = []

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(request: urllib.request.Request, **kwargs: Any) -> Response:
        seen.append((request, kwargs))
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    store = ClickHouseStore(
        base_url="https://clickhouse.example:8443",
        username="service",
        password="synthetic-value",
    )
    assert store.execute("SELECT 1") == b"ok"
    request, options = seen[0]
    assert request.get_full_url().startswith("https://clickhouse.example:8443/")
    assert "synthetic-value" not in request.get_full_url()
    assert request.get_header("X-clickhouse-user") == "service"
    assert request.get_header("X-clickhouse-key") == "synthetic-value"
    context = options["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_development_http_without_credentials_preserves_legacy_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(request: urllib.request.Request, **kwargs: Any) -> Response:
        assert "context" not in kwargs
        assert request.get_header("X-clickhouse-key") is None
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert ClickHouseStore().execute("SELECT 1") == b"ok"


def test_invalid_ca_path_rejected_without_network() -> None:
    with pytest.raises(ValueError, match="CA configuration"):
        ClickHouseStore(
            base_url="https://clickhouse.example:8443",
            ca_file="/missing-cert-configuration.pem",
        )
