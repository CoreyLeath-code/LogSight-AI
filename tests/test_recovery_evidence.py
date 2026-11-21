"""Offline evidence-gate tests; no infrastructure or restore is exercised."""

from __future__ import annotations

from copy import deepcopy

import pytest

from logsight.recovery_evidence import assess_recovery_evidence


def _record() -> dict[str, object]:
    return {
        "environment": "isolated-staging",
        "operator": "staging-operator",
        "reviewer": "staging-reviewer",
        "approval_ticket": "STAGING-CHANGE-123",
        "image_digest": "sha256:" + "a" * 64,
        "git_revision": "a" * 40,
        "dependency": "clickhouse",
        "backup_reference": "backup-synthetic-id",
        "restore_reference": "restore-synthetic-id",
        "started_at_utc": "2026-11-20T12:00:00Z",
        "restored_at_utc": "2026-11-20T12:04:00Z",
        "last_recoverable_at_utc": "2026-11-20T11:59:00Z",
        "rpo_objective_seconds": 120,
        "rto_objective_seconds": 300,
        "data_integrity_verified": True,
        "service_recovered": True,
        "evidence_links": ["https://example.invalid/synthetic-proof"],
    }


def test_assessment_passes_complete_synthetic_record() -> None:
    result = assess_recovery_evidence(_record())
    assert result["status"] == "pass"
    assert result["actual_rpo_seconds"] == 60
    assert result["actual_rto_seconds"] == 240


def test_exceeding_either_objective_is_failure() -> None:
    record = _record()
    record["rpo_objective_seconds"] = 30
    result = assess_recovery_evidence(record)
    assert result["status"] == "fail"
    assert result["meets_rpo"] is False
    assert result["meets_rto"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service_recovered", False),
        ("data_integrity_verified", False),
        ("evidence_links", []),
        ("evidence_links", ["http://not-tls.invalid"]),
        ("rto_objective_seconds", True),
        ("rpo_objective_seconds", -1),
        ("environment", "production"),
        ("operator", ""),
        ("restored_at_utc", "2026-11-20T11:58:00Z"),
        ("last_recoverable_at_utc", "2026-11-20T12:01:00Z"),
        ("started_at_utc", "2026-11-20T12:00:00"),
    ],
)
def test_incomplete_or_invalid_evidence_rejected(field: str, value: object) -> None:
    record = _record()
    record[field] = value
    with pytest.raises(ValueError):
        assess_recovery_evidence(record)


def test_missing_evidence_rejected() -> None:
    record = deepcopy(_record())
    del record["restore_reference"]
    with pytest.raises(ValueError, match="missing recovery evidence fields"):
        assess_recovery_evidence(record)
