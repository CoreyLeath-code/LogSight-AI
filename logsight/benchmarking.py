"""Reproducible labeled-corpus evaluation for LogSight detectors."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from logsight.analyzer import detect_anomalies
from logsight.parser import LogEntry, LogLevel

_MAX_CORPUS_BYTES = 5_000_000
_MAX_RECORDS = 10_000
_MAX_MESSAGE_CHARS = 4_000


@dataclass(frozen=True, slots=True)
class LabeledLog:
    """One synthetic or approved de-identified benchmark record."""

    identifier: str
    level: LogLevel
    message: str
    is_anomaly: bool
    incident_id: str | None = None


@dataclass(frozen=True, slots=True)
class AlertMetrics:
    """Entry- and incident-level quality and alert-volume measurements."""

    total: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float
    incident_recall: float
    alert_count: int
    alerts_per_1000_events: float
    false_alerts_per_1000_events: float
    alerts_per_true_incident: float


def load_labeled_corpus(path: str | Path) -> tuple[LabeledLog, ...]:
    """Load a bounded JSONL corpus and enforce the published label contract."""

    corpus_path = Path(path)
    if not corpus_path.is_file():
        raise FileNotFoundError(f"benchmark corpus was not found: {corpus_path}")
    if corpus_path.stat().st_size > _MAX_CORPUS_BYTES:
        raise ValueError(f"benchmark corpus exceeds {_MAX_CORPUS_BYTES} bytes")

    records: list[LabeledLog] = []
    identifiers: set[str] = set()
    for line_number, line in enumerate(corpus_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        if len(records) >= _MAX_RECORDS:
            raise ValueError(f"benchmark corpus exceeds {_MAX_RECORDS} records")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on benchmark line {line_number}") from exc
        record = _parse_record(raw, line_number)
        if record.identifier in identifiers:
            raise ValueError(f"duplicate benchmark record id: {record.identifier}")
        identifiers.add(record.identifier)
        records.append(record)

    if not records:
        raise ValueError("benchmark corpus must contain at least one record")
    return tuple(records)


def evaluate_labeled_corpus(
    corpus: Sequence[LabeledLog], *, zscore_threshold: float = 2.5
) -> AlertMetrics:
    """Evaluate the built-in detector against immutable labels in a corpus."""

    if not corpus:
        raise ValueError("benchmark corpus must contain at least one record")
    entries = [
        LogEntry(
            raw=f"{record.level.value} {record.message}",
            level=record.level,
            message=record.message,
        )
        for record in corpus
    ]
    alerts = {id(entry) for entry in detect_anomalies(entries, zscore_threshold).anomalies}

    true_positives = sum(
        1 for entry, record in zip(entries, corpus, strict=True) if id(entry) in alerts and record.is_anomaly
    )
    false_positives = sum(
        1
        for entry, record in zip(entries, corpus, strict=True)
        if id(entry) in alerts and not record.is_anomaly
    )
    false_negatives = sum(
        1
        for entry, record in zip(entries, corpus, strict=True)
        if id(entry) not in alerts and record.is_anomaly
    )
    true_negatives = len(corpus) - true_positives - false_positives - false_negatives

    precision = _ratio(true_positives, true_positives + false_positives)
    recall = _ratio(true_positives, true_positives + false_negatives)
    f1 = _ratio(2 * precision * recall, precision + recall)
    true_incidents = {record.incident_id for record in corpus if record.is_anomaly}
    detected_incidents = {
        record.incident_id
        for entry, record in zip(entries, corpus, strict=True)
        if record.is_anomaly and id(entry) in alerts
    }
    alert_count = true_positives + false_positives
    return AlertMetrics(
        total=len(corpus),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        true_negatives=true_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
        incident_recall=_ratio(len(detected_incidents), len(true_incidents)),
        alert_count=alert_count,
        alerts_per_1000_events=1000 * _ratio(alert_count, len(corpus)),
        false_alerts_per_1000_events=1000 * _ratio(false_positives, len(corpus)),
        alerts_per_true_incident=_ratio(alert_count, len(true_incidents)),
    )


def quality_gate_failures(
    metrics: AlertMetrics,
    *,
    min_precision: float | None = None,
    min_recall: float | None = None,
    max_alerts_per_1000_events: float | None = None,
) -> tuple[str, ...]:
    """Return explicit quality-gate failures without choosing deployment policy."""

    _validate_fraction("minimum precision", min_precision)
    _validate_fraction("minimum recall", min_recall)
    if max_alerts_per_1000_events is not None and (
        not isfinite(max_alerts_per_1000_events) or max_alerts_per_1000_events < 0
    ):
        raise ValueError("maximum alerts per 1000 events must be finite and non-negative")

    failures: list[str] = []
    if min_precision is not None and metrics.precision < min_precision:
        failures.append(f"precision {metrics.precision:.4f} is below {min_precision:.4f}")
    if min_recall is not None and metrics.recall < min_recall:
        failures.append(f"recall {metrics.recall:.4f} is below {min_recall:.4f}")
    if (
        max_alerts_per_1000_events is not None
        and metrics.alerts_per_1000_events > max_alerts_per_1000_events
    ):
        failures.append(
            "alerts per 1000 events "
            f"{metrics.alerts_per_1000_events:.4f} exceeds {max_alerts_per_1000_events:.4f}"
        )
    return tuple(failures)


def _parse_record(raw: Any, line_number: int) -> LabeledLog:
    if not isinstance(raw, dict):
        raise ValueError(f"benchmark line {line_number} must be a JSON object")
    identifier = _required_string(raw, "id", line_number)
    message = _required_string(raw, "message", line_number)
    if len(message) > _MAX_MESSAGE_CHARS:
        raise ValueError(f"benchmark line {line_number} message exceeds {_MAX_MESSAGE_CHARS} characters")
    level_name = _required_string(raw, "level", line_number).upper()
    try:
        level = LogLevel(level_name)
    except ValueError as exc:
        raise ValueError(f"benchmark line {line_number} has an invalid level") from exc
    label = raw.get("is_anomaly")
    if type(label) is not bool:
        raise ValueError(f"benchmark line {line_number} requires boolean is_anomaly")
    incident_id = raw.get("incident_id")
    if incident_id is not None and (not isinstance(incident_id, str) or not incident_id.strip()):
        raise ValueError(f"benchmark line {line_number} incident_id must be a non-empty string or null")
    if label and incident_id is None:
        raise ValueError(f"benchmark line {line_number} anomalous records require incident_id")
    return LabeledLog(
        identifier=identifier,
        level=level,
        message=message,
        is_anomaly=label,
        incident_id=incident_id,
    )


def _required_string(raw: dict[str, Any], field: str, line_number: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"benchmark line {line_number} requires a bounded {field}")
    return value.strip()


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator else 0.0


def _validate_fraction(name: str, value: float | None) -> None:
    if value is not None and (not isfinite(value) or not 0 <= value <= 1):
        raise ValueError(f"{name} must be a finite value between zero and one")
