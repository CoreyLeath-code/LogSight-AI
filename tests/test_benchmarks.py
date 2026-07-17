"""Deterministic microbenchmarks for regression tracking."""

from logsight.analyzer import detect_anomalies
from logsight.parser import parse_lines


def test_parse_and_analyze_throughput(benchmark):
    lines = [f"2026-01-01T00:00:00Z INFO service request {i}" for i in range(1_000)]

    def pipeline():
        return detect_anomalies(parse_lines(lines), flag_errors=False)

    result = benchmark(pipeline)
    assert result.stats.total == 1_000
