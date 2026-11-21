"""Validate staging recovery evidence; validation does not perform a restore."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REQUIRED = (
    "environment",
    "operator",
    "reviewer",
    "approval_ticket",
    "image_digest",
    "git_revision",
    "dependency",
    "backup_reference",
    "restore_reference",
    "started_at_utc",
    "restored_at_utc",
    "last_recoverable_at_utc",
    "rpo_objective_seconds",
    "rto_objective_seconds",
    "data_integrity_verified",
    "service_recovered",
    "evidence_links",
)


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must have a UTC timezone")
    return parsed


def assess_recovery_evidence(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on absent proof; return objective results for a real drill."""
    if not isinstance(record, dict):
        raise ValueError("recovery evidence must be a JSON object")
    missing = [key for key in _REQUIRED if key not in record]
    if missing:
        raise ValueError("missing recovery evidence fields: " + ", ".join(missing))
    for field in (
        "environment",
        "operator",
        "reviewer",
        "approval_ticket",
        "image_digest",
        "git_revision",
        "dependency",
        "backup_reference",
        "restore_reference",
    ):
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be non-empty text")
    if record["environment"].lower() in {"production", "prod"}:
        raise ValueError("this evaluator is restricted to staging recovery drills")
    links = record["evidence_links"]
    if not isinstance(links, list) or not links or any(
        not isinstance(link, str) or not link.startswith("https://") or
        not link.strip() for link in links
    ):
        raise ValueError("evidence_links must contain HTTPS evidence references")
    for field in ("data_integrity_verified", "service_recovered"):
        if record[field] is not True:
            raise ValueError(f"{field} must be explicitly verified true")
    for field in ("rpo_objective_seconds", "rto_objective_seconds"):
        if type(record[field]) is not int or record[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    start = _timestamp(record["started_at_utc"], "started_at_utc")
    restored = _timestamp(record["restored_at_utc"], "restored_at_utc")
    recoverable = _timestamp(record["last_recoverable_at_utc"], "last_recoverable_at_utc")
    if restored < start:
        raise ValueError("restored_at_utc predates started_at_utc")
    if recoverable > start:
        raise ValueError("last_recoverable_at_utc cannot be after incident start")
    actual_rto = int((restored - start).total_seconds())
    actual_rpo = int((start - recoverable).total_seconds())
    meets_rto = actual_rto <= record["rto_objective_seconds"]
    meets_rpo = actual_rpo <= record["rpo_objective_seconds"]
    return {
        "status": "pass" if meets_rto and meets_rpo else "fail",
        "dependency": record["dependency"],
        "actual_rpo_seconds": actual_rpo,
        "actual_rto_seconds": actual_rto,
        "meets_rpo": meets_rpo,
        "meets_rto": meets_rto,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate staging recovery evidence")
    parser.add_argument("record", type=Path, help="Local JSON evidence record")
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        assessment = assess_recovery_evidence(record)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"invalid recovery evidence: {exc}\n")
    print(json.dumps(assessment, sort_keys=True))
    return 0 if assessment["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
