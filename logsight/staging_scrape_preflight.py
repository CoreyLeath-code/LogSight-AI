"""Opt-in, read-only API staging preflight; never sends ingestion traffic."""

from __future__ import annotations

import argparse
import os
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_METRIC = "logsight_readiness_success_total"


def validate_target(base_url: str) -> str:
    """Require TLS except for explicit loopback development fixtures."""
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("target must be a base HTTP(S) URL without credentials or path")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("non-loopback staging targets require HTTPS")
    return base_url.rstrip("/")


def _get(url: str, token: str | None = None) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=5, context=ssl.create_default_context()) as response:
            return response.status, response.read(128 * 1024).decode("utf-8", "replace")
    except HTTPError as exc:
        return exc.code, ""
    except (URLError, TimeoutError) as exc:
        raise ValueError("target request failed; inspect secure staging connectivity") from exc


def run_preflight(base_url: str, token: str) -> dict[str, bool]:
    """Check process probes and protected metrics without printing token or payloads."""
    base = validate_target(base_url)
    if not token or len(token) < 32:
        raise ValueError("a staging bearer token of at least 32 characters is required")
    health_code, _ = _get(base + "/health")
    ready_code, _ = _get(base + "/ready")
    unauth_code, _ = _get(base + "/metrics")
    auth_code, metrics = _get(base + "/metrics", token)
    checks = {
        "health_ok": health_code == 200,
        "readiness_ok": ready_code == 200,
        "metrics_unauthorized_without_token": unauth_code == 401,
        "metrics_authenticated": auth_code == 200 and _METRIC in metrics,
    }
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in read-only staging API scrape check")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        token = os.environ.get("LOGSIGHT_STAGING_SCRAPE_TOKEN", "")
        results = run_preflight(args.base_url, token)
    except ValueError as exc:
        parser.exit(2, f"staging preflight failed: {exc}\n")
    for name, ok in results.items():
        print(f"{name}: {'pass' if ok else 'fail'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
