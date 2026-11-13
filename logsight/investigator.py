"""Version-pinned, retrieval-grounded incident investigation helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_MAX_RUNBOOKS = 100
_MAX_RUNBOOK_CHARS = 64_000
_MAX_QUERY_CHARS = 2_000
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
_REVISION = re.compile(r"[A-Za-z0-9._-]{7,64}")


@dataclass(frozen=True, slots=True)
class Runbook:
    """An approved runbook with explicit version and repository provenance."""

    identifier: str
    title: str
    version: str
    revision: str
    path: str
    content: str
    digest: str


@dataclass(frozen=True, slots=True)
class RunbookCitation:
    """A ranked, bounded excerpt suitable for a human incident review."""

    identifier: str
    title: str
    version: str
    revision: str
    path: str
    digest: str
    score: float
    excerpt: str


@dataclass(frozen=True, slots=True)
class Investigation:
    """Evidence-first investigation outcome with immutable source provenance."""

    query: str
    revision: str
    citations: tuple[RunbookCitation, ...]
    guidance: str


class RunbookRepository:
    """Load bounded Markdown runbooks with versioned front matter."""

    def __init__(self, root: str | Path, *, revision: str) -> None:
        self.root = Path(root).resolve()
        if not _REVISION.fullmatch(revision):
            raise ValueError("runbook revision must be a 7-64 character identifier")
        self.revision = revision

    def load(self) -> list[Runbook]:
        """Load approved runbooks under the configured root in stable path order."""

        if not self.root.is_dir():
            raise FileNotFoundError(f"runbook directory was not found: {self.root}")
        paths = sorted(self.root.rglob("*.md"))
        if len(paths) > _MAX_RUNBOOKS:
            raise ValueError(f"runbook directory exceeds {_MAX_RUNBOOKS} documents")
        return [self._load_path(path) for path in paths]

    def _load_path(self, path: Path) -> Runbook:
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("runbook path must stay within the configured directory") from exc
        content = resolved.read_text(encoding="utf-8")
        if len(content) > _MAX_RUNBOOK_CHARS:
            raise ValueError(f"runbook exceeds {_MAX_RUNBOOK_CHARS} characters: {relative_path}")
        metadata, body = _split_front_matter(content)
        identifier = _required_metadata(metadata, "id")
        title = _required_metadata(metadata, "title")
        version = _required_metadata(metadata, "version")
        if not body.strip():
            raise ValueError(f"runbook has no body: {relative_path}")
        return Runbook(
            identifier=identifier,
            title=title,
            version=version,
            revision=self.revision,
            path=relative_path.as_posix(),
            content=body.strip(),
            digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )


class IncidentInvestigator:
    """Retrieve approved runbook excerpts without inventing operational actions."""

    def __init__(self, runbooks: Sequence[Runbook]) -> None:
        self.runbooks = tuple(runbooks)

    def investigate(
        self, query: str, *, evidence: Sequence[str] = (), limit: int = 3
    ) -> Investigation:
        """Rank version-pinned runbooks against an incident query and evidence."""

        if not query.strip() or len(query) > _MAX_QUERY_CHARS:
            raise ValueError("query must be non-empty and within the configured limit")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        query_tokens = _tokens(" ".join([query, *evidence]))
        if not query_tokens:
            raise ValueError("query must contain searchable terms")

        ranked: list[tuple[float, Runbook]] = []
        for runbook in self.runbooks:
            document_tokens = _tokens(f"{runbook.title} {runbook.content}")
            overlap = len(query_tokens & document_tokens)
            if overlap:
                score = overlap / len(query_tokens)
                ranked.append((score, runbook))
        ranked.sort(key=lambda item: (-item[0], item[1].identifier, item[1].path))
        citations = tuple(
            _citation(runbook, score, query_tokens) for score, runbook in ranked[:limit]
        )
        revision = self.runbooks[0].revision if self.runbooks else "none"
        guidance = (
            "Review the cited approved runbook excerpts before acting."
            if citations
            else "No approved runbook matched the supplied incident evidence."
        )
        return Investigation(query=query, revision=revision, citations=citations, guidance=guidance)


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        raise ValueError("runbook must begin with YAML-style front matter")
    closing = content.find("\n---\n", 4)
    if closing < 0:
        raise ValueError("runbook front matter is not terminated")
    metadata: dict[str, str] = {}
    for line in content[4:closing].splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key or not value.strip():
            raise ValueError("runbook front matter must contain key: value entries")
        metadata[key.strip()] = value.strip()
    return metadata, content[closing + 5 :]


def _required_metadata(metadata: dict[str, str], key: str) -> str:
    value = metadata.get(key, "")
    if not value or len(value) > 128:
        raise ValueError(f"runbook metadata requires a bounded {key}")
    return value


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.lower()))


def _citation(runbook: Runbook, score: float, query_tokens: set[str]) -> RunbookCitation:
    lines = runbook.content.splitlines()
    matching = next(
        (line.strip() for line in lines if query_tokens & _tokens(line)),
        lines[0].strip(),
    )
    return RunbookCitation(
        identifier=runbook.identifier,
        title=runbook.title,
        version=runbook.version,
        revision=runbook.revision,
        path=runbook.path,
        digest=runbook.digest,
        score=round(score, 4),
        excerpt=matching[:500],
    )
