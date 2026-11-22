"""Offline gate for owner-reviewed Phase 4 staging rollout evidence.

Never contacts a cluster or proves submitted records are authentic.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an explicit UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an explicit UTC timestamp")
    return parsed


def assess_staging_deployment(record: dict[str, Any]) -> dict[str, Any]:
    """Check declared rollout/monitor readiness without inferring approval."""
    if not isinstance(record, dict):
        raise ValueError("deployment evidence must be a JSON object")
    for field in (
        "environment",
        "namespace",
        "operator",
        "reviewer",
        "approval_ticket",
        "helm_release",
        "values_revision",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
    if record["environment"].strip().lower() in {"prod", "production"}:
        raise ValueError("this gate is only for non-production staging")
    if record["operator"].strip() == record["reviewer"].strip():
        raise ValueError("operator and reviewer must be distinct")
    if not isinstance(record.get("git_revision"), str) or not _SHA.fullmatch(
        record["git_revision"]
    ):
        raise ValueError("git_revision must be a full 40-character commit SHA")

    expected = record.get("expected_image")
    observed = record.get("observed_image")
    if not isinstance(expected, str) or not _IMAGE.fullmatch(expected):
        raise ValueError("expected_image must be a digest-pinned OCI image")
    if observed != expected:
        raise ValueError("observed_image must equal expected_image exactly")

    desired = record.get("desired_replicas")
    ready = record.get("ready_replicas")
    updated = record.get("updated_replicas")
    if type(desired) is not int or desired < 1:
        raise ValueError("desired_replicas must be a positive integer")
    for field, count in (("ready_replicas", ready), ("updated_replicas", updated)):
        if type(count) is not int or count < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    for field in ("rollout_completed", "authenticated_scrape_observed"):
        if record.get(field) is not True:
            raise ValueError(f"{field} must be explicitly confirmed")

    started = _utc(record.get("rollout_started_at_utc"), "rollout_started_at_utc")
    finished = _utc(record.get("rollout_finished_at_utc"), "rollout_finished_at_utc")
    if finished < started:
        raise ValueError("rollout completion precedes start")
    links = record.get("evidence_links")
    if not isinstance(links, list) or not links or any(
        not isinstance(link, str) or not link.startswith("https://") for link in links
    ):
        raise ValueError("nonempty HTTPS evidence links are required")
    healthy = ready >= desired and updated == desired
    return {
        "status": "pass" if healthy else "fail",
        "replicas_ready": healthy,
        "digest_matches": True,
        "authenticated_scrape_declared": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a non-production staging rollout record")
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.record.read_text(encoding="utf-8"))
        result = assess_staging_deployment(data)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid staging deployment evidence: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
