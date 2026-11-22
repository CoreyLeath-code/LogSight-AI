"""Read-only authenticated Prometheus target-health observation for isolated staging.

No configuration is changed and Prometheus response bodies are not logged.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    """Disallow redirects that could forward an Authorization header."""

    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def validate_prometheus_url(base_url: str) -> str:
    """Require HTTPS outside loopback and reject embedded credentials or URL paths."""
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Prometheus URL must be a bare HTTP(S) origin without credentials")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("non-loopback Prometheus API must use HTTPS")
    return base_url.rstrip("/")


def assess_prometheus_target(
    response: dict[str, Any], expected_job: str, expected_instance: str
) -> dict[str, Any]:
    """Evaluate one exact active scrape target; never echo scrape URLs or labels."""
    if not expected_job.strip() or not expected_instance.strip():
        raise ValueError("approved job and instance labels are required")
    if response.get("status") != "success":
        raise ValueError("Prometheus API did not report success")
    data = response.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("activeTargets"), list):
        raise ValueError("Prometheus activeTargets response is invalid")
    candidates = [
        target
        for target in data["activeTargets"]
        if isinstance(target, dict)
        and isinstance(target.get("labels"), dict)
        and target["labels"].get("job") == expected_job
        and target["labels"].get("instance") == expected_instance
    ]
    if len(candidates) != 1:
        raise ValueError("expected exactly one matching active Prometheus target")
    target = candidates[0]
    scrape_url = target.get("scrapeUrl")
    if not isinstance(scrape_url, str) or urlsplit(scrape_url).path != "/metrics":
        raise ValueError("matching scrape target does not use /metrics")
    observed = target.get("lastScrape")
    if not isinstance(observed, str) or not observed.strip():
        raise ValueError("no lastScrape timestamp was observed")
    healthy = target.get("health") == "up" and not target.get("lastError")
    return {
        "status": "pass" if healthy else "fail",
        "target_count": 1,
        "job": expected_job,
        "instance": expected_instance,
        "scrape_health_up": target.get("health") == "up",
        "scrape_error_empty": not bool(target.get("lastError")),
        "last_scrape_recorded": True,
        "independent_service_sli_verified": False,
    }


def observe_target(base_url: str, token: str, job: str, instance: str) -> dict[str, Any]:
    """Query only Prometheus /api/v1/targets with a bearer credential."""
    base = validate_prometheus_url(base_url)
    if not token:
        raise ValueError("PROMETHEUS_STAGING_TOKEN must be set")
    req = Request(
        base + "/api/v1/targets?state=active",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=8) as response:
            if response.status != 200:
                raise ValueError("Prometheus API returned a non-success HTTP status")
            contents = response.read(1024 * 1024 + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError("Prometheus target read failed; verify staging API access") from exc
    if len(contents) > 1024 * 1024:
        raise ValueError("Prometheus target response exceeded size limit")
    try:
        payload = json.loads(contents)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Prometheus target response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Prometheus target response must be an object")
    return assess_prometheus_target(payload, job, instance)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only staging Prometheus scrape check")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()
    try:
        result = observe_target(
            args.base_url,
            os.environ.get("PROMETHEUS_STAGING_TOKEN", ""),
            args.job,
            args.instance,
        )
    except ValueError as exc:
        parser.exit(2, f"staging Prometheus check rejected: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
