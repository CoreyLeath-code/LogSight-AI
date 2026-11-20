"""Tests for the metadata-only DLQ command-line entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from logsight.dead_letter import quarantine_envelope
from logsight.dlq_inspect import main


def test_command_prints_verified_metadata_without_raw_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "restricted.json"
    file.write_bytes(
        quarantine_envelope(
            b"password=secret-dont-print@example.test", topic="logs", partition=1, offset=3
        )
    )
    monkeypatch.setattr(sys, "argv", ["dlq-inspect", str(file)])
    assert main() == 0
    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert summary["verified"] is True
    assert summary["source"]["offset"] == 3
    assert "secret-dont-print" not in output.out
    assert output.err == ""


@pytest.mark.parametrize("kind", ["missing", "invalid", "oversized"])
def test_command_fails_without_disclosing_payloads(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    file = tmp_path / "restricted.json"
    if kind == "invalid":
        file.write_text('{"payload_base64":"private-value"}')
    elif kind == "oversized":
        file.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "argv", ["dlq-inspect", str(file)])
    assert main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid or inaccessible envelope" in output.err
    assert "private-value" not in output.err
