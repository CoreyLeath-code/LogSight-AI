"""Anomaly detection and statistical analysis for parsed log streams."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from statistics import fmean, pstdev

from logsight.parser import LogEntry, LogLevel


@dataclass
class WindowStats:
    """Summary statistics for a sliding window of log entries."""

    total: int = 0
    error_count: int = 0
    warning_count: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)
    top_messages: list[tuple[str, int]] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.error_count / self.total if self.total else 0.0


@dataclass
class AnomalyReport:
    """Result of an anomaly scan over a sequence of log entries."""

    anomalies: list[LogEntry] = field(default_factory=list)
    stats: WindowStats = field(default_factory=WindowStats)
    zscore_threshold: float = 2.5

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0


def compute_stats(entries: Sequence[LogEntry]) -> WindowStats:
    """Return summary statistics for *entries*."""
    stats = WindowStats(total=len(entries))
    level_counter: Counter[str] = Counter()
    message_counter: Counter[str] = Counter()

    for entry in entries:
        level_counter[entry.level.value] += 1
        if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
            stats.error_count += 1
        elif entry.level == LogLevel.WARNING:
            stats.warning_count += 1
        # Truncate message to avoid huge keys.
        msg_key = entry.message[:120].strip()
        if msg_key:
            message_counter[msg_key] += 1

    stats.level_counts = dict(level_counter)
    stats.top_messages = message_counter.most_common(10)
    return stats


def _message_lengths(entries: Sequence[LogEntry]) -> list[float]:
    return [float(len(e.message)) for e in entries]


def detect_anomalies(
    entries: Sequence[LogEntry],
    zscore_threshold: float = 2.5,
    flag_errors: bool = True,
) -> AnomalyReport:
    """Detect anomalous log entries using z-score on message length.

    Entries whose message length deviates more than *zscore_threshold*
    standard deviations from the mean are flagged, together with any
    ERROR / CRITICAL entries when *flag_errors* is ``True``.

    Parameters
    ----------
    entries:
        Sequence of :class:`~logsight.parser.LogEntry` objects.
    zscore_threshold:
        Number of standard deviations above the mean that triggers an
        anomaly flag.  Defaults to ``2.5``.
    flag_errors:
        When ``True`` (default), ERROR and CRITICAL entries are always
        included in the anomaly list regardless of z-score.

    Returns
    -------
    AnomalyReport
    """
    if not isfinite(zscore_threshold) or zscore_threshold < 0:
        raise ValueError("zscore_threshold must be a finite, non-negative number")

    report = AnomalyReport(zscore_threshold=zscore_threshold)
    report.stats = compute_stats(entries)

    if not entries:
        return report

    lengths = _message_lengths(entries)
    mean = fmean(lengths)
    std = pstdev(lengths)

    anomalous: list[LogEntry] = []
    seen_ids: set[int] = set()

    for entry in entries:
        flagged = False
        if flag_errors and entry.is_error:
            flagged = True
        if std > 0:
            z = abs(len(entry.message) - mean) / std
            if z > zscore_threshold:
                flagged = True
        if flagged and id(entry) not in seen_ids:
            anomalous.append(entry)
            seen_ids.add(id(entry))

    report.anomalies = anomalous
    return report


def error_rate_spike(
    entries: Sequence[LogEntry],
    window_size: int = 100,
    spike_threshold: float = 0.25,
) -> list[int]:
    """Return the starting indices of windows whose error rate exceeds *spike_threshold*.

    Parameters
    ----------
    entries:
        Sequence of :class:`~logsight.parser.LogEntry` objects.
    window_size:
        Number of entries per sliding window.
    spike_threshold:
        Fraction of errors that triggers a spike (``0.0``â€“``1.0``).

    Returns
    -------
    List of start indices where a spike was detected.
    """
    if window_size <= 0:
        raise ValueError("window_size must be greater than zero")
    if not 0 <= spike_threshold <= 1:
        raise ValueError("spike_threshold must be between 0 and 1")

    spike_starts: list[int] = []
    n = len(entries)
    for start in range(0, n - window_size + 1, window_size):
        window = entries[start : start + window_size]
        errors = sum(1 for e in window if e.is_error)
        rate = errors / window_size
        if rate >= spike_threshold:
            spike_starts.append(start)
    return spike_starts
