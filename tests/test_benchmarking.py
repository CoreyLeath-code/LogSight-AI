"""Tests for labeled corpus benchmarking and quality gates."""

from __future__ import annotations

import json

import pytest

from logsight.benchmarking import (
    LabeledLog,
    evaluate_labeled_corpus,
    load_labeled_corpus,
    quality_gate_failures,
)
from logsight.parser import LogLevel


def _record(
    identifier: str,
    *,
    level: str = "INFO",
    is_anomaly: bool = False,
    incident_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": identifier,
        "level": level,
        "message": "steady service request completed normally",
        "is_anomaly": is_anomaly,
        "incident_id": incident_id,
    }


def test_loads_valid_jsonl_corpus(tmp_path) -> None:
    corpus_file = tmp_path / "corpus.jsonl"
    corpus_file.write_text(
        "\n".join(
            [
                json.dumps(_record("normal-1")),
                json.dumps(
                    _record(
                        "incident-1",
                        level="ERROR",
                        is_anomaly=True,
                        incident_id="database-timeout",
                    )
                ),
            ]
        ),
        encoding="utf-8",
    )

    corpus = load_labeled_corpus(corpus_file)

    assert len(corpus) == 2
    assert corpus[1].level is LogLevel.ERROR
    assert corpus[1].incident_id == "database-timeout"


def test_calculates_precision_recall_and_alert_burden() -> None:
    corpus = (
        LabeledLog("true-positive", LogLevel.ERROR, "same length message", True, "incident-a"),
        LabeledLog("false-positive", LogLevel.ERROR, "same length message", False),
        LabeledLog("false-negative", LogLevel.WARNING, "same length message", True, "incident-b"),
        LabeledLog("true-negative", LogLevel.INFO, "same length message", False),
    )

    metrics = evaluate_labeled_corpus(corpus)

    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.true_negatives == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
    assert metrics.incident_recall == 0.5
    assert metrics.alert_count == 2
    assert metrics.alerts_per_1000_events == 500
    assert metrics.false_alerts_per_1000_events == 250
    assert metrics.alerts_per_true_incident == 1


def test_quality_gate_failures_are_explicit() -> None:
    metrics = evaluate_labeled_corpus(
        (
            LabeledLog("alert", LogLevel.ERROR, "same length message", True, "incident-a"),
            LabeledLog("normal", LogLevel.INFO, "same length message", False),
        )
    )

    assert quality_gate_failures(metrics, min_precision=1, min_recall=1) == ()
    failures = quality_gate_failures(
        metrics,
        min_precision=1,
        min_recall=1,
        max_alerts_per_1000_events=400,
    )

    assert failures == ("alerts per 1000 events 500.0000 exceeds 400.0000",)


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "at least one"),
        ([{"id": "bad"}], "bounded message"),
        ([_record("duplicate"), _record("duplicate")], "duplicate"),
        ([_record("missing-incident", is_anomaly=True)], "require incident_id"),
        ([_record("invalid-label", is_anomaly=1)], "boolean"),
    ],
)
def test_rejects_invalid_corpus_records(tmp_path, records, message: str) -> None:
    corpus_file = tmp_path / "corpus.jsonl"
    corpus_file.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_labeled_corpus(corpus_file)


def test_rejects_missing_or_malformed_corpus(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_labeled_corpus(tmp_path / "missing.jsonl")

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("{not json}", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_labeled_corpus(malformed)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"min_precision": -0.1}, "minimum precision"),
        ({"min_recall": 1.1}, "minimum recall"),
        ({"max_alerts_per_1000_events": -1}, "maximum alerts"),
    ],
)
def test_rejects_invalid_quality_gates(kwargs, message: str) -> None:
    metrics = evaluate_labeled_corpus(
        (LabeledLog("normal", LogLevel.INFO, "same length message", False),)
    )

    with pytest.raises(ValueError, match=message):
        quality_gate_failures(metrics, **kwargs)


def test_rejects_empty_in_memory_corpus() -> None:
    with pytest.raises(ValueError, match="at least one"):
        evaluate_labeled_corpus(())
