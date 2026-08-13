"""Tests for evidence-backed LogSight explanations."""

from __future__ import annotations

from logsight.analyzer import detect_anomalies, error_rate_spike_details
from logsight.parser import parse_line
from logsight.reasoning import explain_report


def _entry(level: str, message: str):
    return parse_line(f"{level} {message}")


def test_explains_direct_error_evidence_without_causal_claim():
    report = detect_anomalies([_entry("ERROR", "database connection failed")])

    explanations = explain_report(report)

    assert len(explanations) == 1
    assert explanations[0].category == "error-level"
    assert explanations[0].evidence_strength == "direct"
    assert explanations[0].support_level == "single-signal"
    assert "level=ERROR" in explanations[0].evidence
    assert "no root cause is inferred" in explanations[0].summary


def test_explains_statistical_outlier_and_error_rate_spike():
    entries = [_entry("INFO", "normal log line")] * 50 + [
        _entry("ERROR", "x" * 500),
        _entry("ERROR", "failed"),
        _entry("INFO", "ok"),
        _entry("INFO", "ok"),
    ]
    report = detect_anomalies(entries, zscore_threshold=2.0)
    spikes = error_rate_spike_details(entries[-4:], window_size=4, spike_threshold=0.5)

    explanations = explain_report(report, spikes)

    categories = {explanation.category for explanation in explanations}
    assert "error-level" in categories
    assert "message-length-outlier" in categories
    assert "error-rate-spike" in categories
    spike = next(item for item in explanations if item.category == "error-rate-spike")
    assert "errors=2" in spike.evidence
    assert "entries=4" in spike.evidence


def test_returns_no_explanations_when_detector_has_no_findings():
    report = detect_anomalies([_entry("INFO", "healthy")])

    assert explain_report(report) == []


def test_marks_two_detector_signals_as_corroborated():
    entries = [_entry("INFO", "normal")] * 20 + [_entry("ERROR", "x" * 500)]
    report = detect_anomalies(entries, zscore_threshold=2.0)

    explanations = explain_report(report)

    assert any(item.support_level == "corroborated" for item in explanations)
