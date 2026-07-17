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
