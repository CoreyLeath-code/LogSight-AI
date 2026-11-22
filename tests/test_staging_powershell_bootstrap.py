"""Offline Windows staging bootstrap contracts; never run PowerShell in CI."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/bootstrap_local_staging_alerts.ps1"


def test_windows_bootstrap_explicit_opt_in_and_local_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$Execute" in source
    assert "if (-not $Execute)" in source
    assert source.index("if (-not $Execute)") < source.index("& kind create cluster")
    assert "if ($existing -contains $cluster)" in source
    assert "& docker info" in source
    assert "kind-config.yaml" in source
    assert "kind-alerts.yaml" in source
    assert "staging_test_receiver.py" in source
    assert "port-forward --address 127.0.0.1" in source
    assert "logsight-staging-alerts" in source
    assert "logsight-staging" in source
    assert "--context $context" in source
    assert "ALERTMANAGER_STAGING_TOKEN" not in source
    assert "SEND_SYNTHETIC_STAGING_ALERT" not in source


def test_bash_scripts_checkout_with_unix_line_endings() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
