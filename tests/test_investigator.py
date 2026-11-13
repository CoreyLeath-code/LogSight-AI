"""Tests for the version-pinned incident investigator."""

from __future__ import annotations

import pytest

from logsight.investigator import IncidentInvestigator, RunbookRepository


def _write_runbook(
    root,
    name: str,
    *,
    identifier: str = "database-timeout",
    title: str = "Database timeout response",
    version: str = "1.2.0",
    body: str = "Confirm database connection saturation before escalating.",
) -> None:
    (root / name).write_text(
        "\n".join(
            [
                "---",
                f"id: {identifier}",
                f"title: {title}",
                f"version: {version}",
                "---",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_loads_versioned_runbook_with_digest_and_relative_path(tmp_path) -> None:
    _write_runbook(tmp_path, "database.md")

    runbook = RunbookRepository(tmp_path, revision="abcdef1").load()[0]

    assert runbook.identifier == "database-timeout"
    assert runbook.version == "1.2.0"
    assert runbook.revision == "abcdef1"
    assert runbook.path == "database.md"
    assert len(runbook.digest) == 64


def test_investigation_ranks_grounded_citations_deterministically(tmp_path) -> None:
    _write_runbook(
        tmp_path,
        "queue.md",
        identifier="queue-backlog",
        title="Queue backlog response",
        version="2.0.0",
        body="Inspect consumer lag and retain the evidence in the incident timeline.",
    )
    _write_runbook(tmp_path, "database.md")

    investigation = IncidentInvestigator(
        RunbookRepository(tmp_path, revision="0123456789abcdef").load()
    ).investigate(
        "database timeout",
        evidence=("connection saturation observed",),
        limit=2,
    )

    assert investigation.revision == "0123456789abcdef"
    assert [citation.identifier for citation in investigation.citations] == ["database-timeout"]
    citation = investigation.citations[0]
    assert citation.version == "1.2.0"
    assert citation.digest
    assert "database connection saturation" in citation.excerpt.lower()
    assert investigation.guidance.startswith("Review the cited")


def test_investigation_returns_no_ungrounded_guidance_for_no_match(tmp_path) -> None:
    _write_runbook(tmp_path, "database.md")

    investigation = IncidentInvestigator(
        RunbookRepository(tmp_path, revision="abcdef1").load()
    ).investigate("kubernetes deployment")

    assert investigation.citations == ()
    assert investigation.guidance == "No approved runbook matched the supplied incident evidence."


def test_investigation_with_no_runbooks_records_no_revision() -> None:
    investigation = IncidentInvestigator(()).investigate("database timeout")

    assert investigation.revision == "none"
    assert investigation.citations == ()


@pytest.mark.parametrize(
    ("revision", "message"),
    [
        ("short", "7-64"),
        ("not allowed!", "7-64"),
    ],
)
def test_rejects_invalid_repository_revision(tmp_path, revision: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        RunbookRepository(tmp_path, revision=revision)


def test_rejects_missing_runbook_directory(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        RunbookRepository(tmp_path / "missing", revision="abcdef1").load()


@pytest.mark.parametrize(
    "content",
    [
        "not front matter",
        "---\nid: database\ntitle: Database\nversion: 1",
        "---\nid:\ntitle: Database\nversion: 1\n---\nbody",
        "---\nid: database\ntitle: Database\n---\nbody",
        "---\nid: database\ntitle: Database\nversion: 1\n---\n",
    ],
)
def test_rejects_invalid_or_incomplete_runbooks(tmp_path, content: str) -> None:
    (tmp_path / "invalid.md").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        RunbookRepository(tmp_path, revision="abcdef1").load()


def test_rejects_oversized_runbook(tmp_path) -> None:
    _write_runbook(tmp_path, "large.md", body="x" * 64_001)

    with pytest.raises(ValueError, match="exceeds"):
        RunbookRepository(tmp_path, revision="abcdef1").load()


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "non-empty"),
        ("x", 1, "searchable"),
        ("database", 0, "between"),
        ("database", 11, "between"),
    ],
)
def test_rejects_invalid_queries_and_limits(tmp_path, query: str, limit: int, message: str) -> None:
    _write_runbook(tmp_path, "database.md")
    investigator = IncidentInvestigator(RunbookRepository(tmp_path, revision="abcdef1").load())

    with pytest.raises(ValueError, match=message):
        investigator.investigate(query, limit=limit)
