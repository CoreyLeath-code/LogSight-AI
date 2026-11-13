"""Pluggable log-template parsers with an optional stateful Drain3 adapter."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any, Protocol, cast

from .enterprise import extract_template


class TemplateParser(Protocol):
    """Template parser contract used by the ingestion path."""

    def parse(self, message: str) -> str:
        """Return a normalized template for one log message."""


class _Drain3Miner(Protocol):
    def add_log_message(self, log_message: str) -> dict[str, Any]:
        """Update parser state and return Drain3's match result."""


class BaselineTemplateParser:
    """Dependency-free parser that preserves LogSight's current behavior."""

    def parse(self, message: str) -> str:
        return extract_template(message)


class Drain3TemplateParser:
    """Thread-safe adapter around Drain3's stateful template miner.

    The parser is intentionally created once per worker. Drain3 mutates its
    cluster state while parsing, so access is serialized within that worker.
    Multi-worker deployments should persist and coordinate Drain3 state through
    the deployment's chosen state-management boundary.
    """

    def __init__(
        self,
        template_miner: _Drain3Miner | None = None,
        *,
        config_path: str | Path | None = None,
    ) -> None:
        self._miner = template_miner or self._create_miner(config_path)
        self._lock = Lock()

    @staticmethod
    def _create_miner(config_path: str | Path | None) -> _Drain3Miner:
        try:
            from drain3 import TemplateMiner
            from drain3.template_miner_config import TemplateMinerConfig
        except ImportError as exc:
            raise RuntimeError(
                "Install the parsing extra to enable the Drain3 template parser"
            ) from exc

        config = TemplateMinerConfig()
        if config_path:
            config.load(str(config_path))
        return cast(_Drain3Miner, TemplateMiner(config=config))

    def parse(self, message: str) -> str:
        with self._lock:
            result = self._miner.add_log_message(message)
        template = result.get("template_mined")
        if not isinstance(template, str) or not template:
            raise RuntimeError("Drain3 did not return a usable template")
        return template


def build_template_parser(
    backend: str | None = None, config_path: str | Path | None = None
) -> TemplateParser:
    """Build the selected parser from explicit values or deployment settings.

    Baseline is the safe default. Drain3 requires the optional parsing
    dependency and fails fast when it cannot be initialized.
    """

    configured_backend = backend if backend is not None else os.getenv("LOGSIGHT_TEMPLATE_PARSER")
    selected = (configured_backend or "baseline").strip().lower()
    resolved_config = config_path or os.getenv("LOGSIGHT_DRAIN3_CONFIG")
    if selected == "baseline":
        return BaselineTemplateParser()
    if selected == "drain3":
        return Drain3TemplateParser(config_path=resolved_config)
    raise ValueError("LOGSIGHT_TEMPLATE_PARSER must be 'baseline' or 'drain3'")
