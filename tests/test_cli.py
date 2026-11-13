"""Tests for logsight.cli."""

from __future__ import annotations

from click.testing import CliRunner

from logsight.cli import main


class TestHealthCommand:
    def test_health_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0

    def test_health_output_contains_healthy(self):
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert "healthy" in result.output.lower()

    def test_health_output_contains_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert "version" in result.output.lower()


class TestAnalyzeCommand:
    def test_analyzes_file_and_reports_spike(self, tmp_path):
        log_file = tmp_path / "events.log"
        log_file.write_text("ERROR failed\nERROR failed again\n", encoding="utf-8")
        result = CliRunner().invoke(
            main,
            ["analyze", str(log_file), "--window", "1", "--spike-threshold", "1"],
        )
        assert result.exit_code == 0
        assert "Anomalies detected" in result.output
        assert "Error-rate spikes" in result.output

    def test_empty_file(self, tmp_path):
        log_file = tmp_path / "empty.log"
        log_file.write_text("", encoding="utf-8")
        result = CliRunner().invoke(main, ["analyze", str(log_file)])
        assert result.exit_code == 0
        assert "No log entries" in result.output

    def test_rejects_invalid_window(self, tmp_path):
        log_file = tmp_path / "events.log"
        log_file.write_text("INFO ok", encoding="utf-8")
        result = CliRunner().invoke(main, ["analyze", str(log_file), "--window", "0"])
        assert result.exit_code == 2


class TestStdinCommand:
    def test_analyzes_stdin(self):
        result = CliRunner().invoke(main, ["stdin"], input="INFO ok\nERROR failed\n")
        assert result.exit_code == 0
        assert "Total entries" in result.output

    def test_empty_stdin(self):
        result = CliRunner().invoke(main, ["stdin"], input="\n")
        assert result.exit_code == 0
        assert "No log entries" in result.output

    def test_explain_uses_detector_evidence(self, tmp_path):
        log_file = tmp_path / "events.log"
        log_file.write_text("ERROR database connection failed\n", encoding="utf-8")
        result = CliRunner().invoke(main, ["analyze", str(log_file), "--explain"])
        assert result.exit_code == 0
        assert "Evidence-backed findings" in result.output
        assert "level=ERROR" in result.output
        assert "single-signal" in result.output
        assert "no root cause is inferred" in " ".join(result.output.split())


class TestInvestigateCommand:
    def test_returns_versioned_grounded_citation(self, tmp_path):
        runbook = tmp_path / "database.md"
        runbook.write_text(
            "\n".join(
                [
                    "---",
                    "id: database-timeout",
                    "title: Database timeout response",
                    "version: 1.0.0",
                    "---",
                    "Confirm database connection saturation before escalating.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        result = CliRunner().invoke(
            main,
            [
                "investigate",
                "database timeout",
                "--runbooks",
                str(tmp_path),
                "--revision",
                "abcdef1",
            ],
        )

        assert result.exit_code == 0
        assert "Investigation provenance" in result.output
        assert "database-timeout v1.0.0" in result.output
        assert "abcdef1" in result.output
        assert "digest" in result.output.lower()

    def test_rejects_invalid_runbook_revision(self, tmp_path):
        result = CliRunner().invoke(
            main,
            [
                "investigate",
                "database timeout",
                "--runbooks",
                str(tmp_path),
                "--revision",
                "short",
            ],
        )

        assert result.exit_code == 1
        assert "7-64 character identifier" in result.output


class TestBenchmarkCommand:
    def test_reports_quality_and_alert_burden_metrics(self, tmp_path):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(
            "\n".join(
                [
                    '{"id":"normal","level":"INFO","message":"same length message","is_anomaly":false,"incident_id":null}',
                    '{"id":"alert","level":"ERROR","message":"same length message","is_anomaly":true,"incident_id":"incident-a"}',
                ]
            ),
            encoding="utf-8",
        )

        result = CliRunner().invoke(main, ["benchmark", "--corpus", str(corpus)])

        assert result.exit_code == 0
        assert "Labeled benchmark results" in result.output
        assert "precision / recall / F1" in result.output
        assert "alerts per 1,000 events" in result.output

    def test_fails_when_a_quality_gate_is_not_met(self, tmp_path):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(
            '{"id":"normal","level":"INFO","message":"same length message","is_anomaly":false,"incident_id":null}',
            encoding="utf-8",
        )

        result = CliRunner().invoke(
            main,
            [
                "benchmark",
                "--corpus",
                str(corpus),
                "--min-recall",
                "0.1",
            ],
        )

        assert result.exit_code == 1
        assert "benchmark quality gate failed" in result.output
