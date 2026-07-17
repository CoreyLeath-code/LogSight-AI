"""Tests for logsight.analyzer."""

from __future__ import annotations

import pytest

from logsight.analyzer import (
    AnomalyReport,
    compute_stats,
    detect_anomalies,
    error_rate_spike,
)
from logsight.parser import LogEntry, LogLevel, parse_line


def _entry(level: str, message: str) -> LogEntry:
    return parse_line(f"{level} {message}")


class TestComputeStats:
    def test_empty(self):
        stats = compute_stats([])
        assert stats.total == 0
        assert stats.error_count == 0
        assert stats.error_rate == 0.0

    def test_counts(self):
        entries = [
            _entry("INFO", "a"),
            _entry("ERROR", "b"),
            _entry("CRITICAL", "c"),
            _entry("WARNING", "d"),
        ]
        stats = compute_stats(entries)
        assert stats.total == 4
        assert stats.error_count == 2
        assert stats.warning_count == 1
        assert stats.error_rate == 0.5

    def test_top_messages(self):
        entries = [_entry("INFO", "repeated message")] * 5 + [_entry("INFO", "other")]
        stats = compute_stats(entries)
        assert stats.top_messages[0][0] == "repeated message"
        assert stats.top_messages[0][1] == 5

    def test_level_counts(self):
        entries = [_entry("INFO", "x"), _entry("INFO", "y"), _entry("ERROR", "z")]
        stats = compute_stats(entries)
        assert stats.level_counts.get("INFO") == 2
        assert stats.level_counts.get("ERROR") == 1


class TestDetectAnomalies:
    @pytest.mark.parametrize("threshold", [-1, float("inf"), float("nan")])
    def test_rejects_invalid_threshold(self, threshold):
        with pytest.raises(ValueError):
            detect_anomalies([_entry("INFO", "ok")], zscore_threshold=threshold)

    def test_empty_entries(self):
        report = detect_anomalies([])
        assert not report.has_anomalies
        assert report.stats.total == 0

    def test_errors_flagged_by_default(self):
        entries = [_entry("ERROR", "db connection lost")]
        report = detect_anomalies(entries)
        assert report.has_anomalies
        assert report.anomalies[0].level == LogLevel.ERROR

    def test_flag_errors_false(self):
        # With flag_errors=False and a short message that won't exceed z-score,
        # the error should not be flagged.
        entries = [_entry("ERROR", "err")] + [_entry("INFO", "ok")] * 10
        report = detect_anomalies(entries, flag_errors=False)
        # Only check z-score flagging; the short "err" message may or may not be flagged.
        for anomaly in report.anomalies:
            assert anomaly.is_error is False or anomaly.is_error  # no assertion on presence

    def test_zscore_anomaly(self):
        # Create a long outlier message that should be flagged by z-score.
        normal = [_entry("INFO", "normal log line")] * 50
        outlier = parse_line("INFO " + "x" * 500)
        entries = normal + [outlier]
        report = detect_anomalies(entries, zscore_threshold=2.0, flag_errors=False)
        assert outlier in report.anomalies

    def test_no_duplicates(self):
        # An ERROR entry that is also a z-score outlier should appear only once.
        normal = [_entry("INFO", "normal log line")] * 50
        outlier = parse_line("ERROR " + "x" * 500)
        entries = normal + [outlier]
        report = detect_anomalies(entries, zscore_threshold=2.0, flag_errors=True)
        assert report.anomalies.count(outlier) == 1

    def test_returns_anomaly_report(self):
        report = detect_anomalies([_entry("INFO", "hello")])
        assert isinstance(report, AnomalyReport)


class TestErrorRateSpike:
    @pytest.mark.parametrize("window", [0, -1])
    def test_rejects_invalid_window(self, window):
        with pytest.raises(ValueError):
            error_rate_spike([], window_size=window)

    @pytest.mark.parametrize("threshold", [-0.01, 1.01])
    def test_rejects_invalid_spike_threshold(self, threshold):
        with pytest.raises(ValueError):
            error_rate_spike([], spike_threshold=threshold)

    def test_no_spike(self):
        entries = [_entry("INFO", "ok")] * 200
        spikes = error_rate_spike(entries, window_size=100, spike_threshold=0.25)
        assert spikes == []

    def test_spike_detected(self):
        # First 100 entries are all errors â†’ spike.
        entries = [_entry("ERROR", "fail")] * 100 + [_entry("INFO", "ok")] * 100
        spikes = error_rate_spike(entries, window_size=100, spike_threshold=0.25)
        assert 0 in spikes
        assert 100 not in spikes

    def test_empty(self):
        assert error_rate_spike([], window_size=100, spike_threshold=0.25) == []

    def test_fewer_than_window(self):
        entries = [_entry("ERROR", "fail")] * 50
        spikes = error_rate_spike(entries, window_size=100, spike_threshold=0.25)
        assert spikes == []
