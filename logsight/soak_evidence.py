"""Offline staging soak acceptance checks; this module does not generate load."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def assess_soak_evidence(record: dict[str, Any]) -> dict[str, Any]:
    """Validate declared sample totals and approved SLO limits, failing closed."""
    if not isinstance(record, dict):
        raise ValueError("soak evidence must be a JSON object")
    text_fields = (
        "environment",
        "operator",
        "reviewer",
        "approval_ticket",
        "git_revision",
        "image_digest",
        "load_profile_reference",
    )
    for field in text_fields:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} is required")
    if record["environment"].strip().lower() in {"prod", "production"}:
        raise ValueError("only non-production soak records are accepted")
    numeric_fields = (
        "requests_total",
        "requests_successful",
        "requests_failed",
        "duration_seconds",
        "p95_latency_ms",
        "approved_min_success_ratio",
        "approved_max_p95_latency_ms",
        "approved_min_duration_seconds",
    )
    for field in numeric_fields:
        value = record.get(field)
        if type(value) not in (int, float) or value < 0:
            raise ValueError(f"{field} must be a non-negative number")
    total = record["requests_total"]
    if total < 1 or record["duration_seconds"] <= 0:
        raise ValueError("soak evidence needs nonzero requests and duration")
    if record["requests_successful"] + record["requests_failed"] != total:
        raise ValueError("success and failure counts must equal total requests")
    if record["approved_min_success_ratio"] > 1:
        raise ValueError("success ratio objective must be between 0 and 1")
    evidence_links = record.get("evidence_links")
    if not isinstance(evidence_links, list) or not evidence_links or any(
        not isinstance(link, str) or not link.startswith("https://")
        for link in evidence_links
    ):
        raise ValueError("HTTPS evidence links are required")
    if record.get("dependency_recovery_verified") is not True:
        raise ValueError("dependency recovery must be explicitly verified")
    success_ratio = record["requests_successful"] / total
    meets_ratio = success_ratio >= record["approved_min_success_ratio"]
    meets_latency = record["p95_latency_ms"] <= record["approved_max_p95_latency_ms"]
    meets_duration = record["duration_seconds"] >= record["approved_min_duration_seconds"]
    return {
        "status": "pass" if all((meets_ratio, meets_latency, meets_duration)) else "fail",
        "success_ratio": round(success_ratio, 6),
        "meets_success_ratio": meets_ratio,
        "meets_p95_latency": meets_latency,
        "meets_duration": meets_duration,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate isolated staging soak records")
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        report = assess_soak_evidence(json.loads(args.record.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid soak evidence: {exc}\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
