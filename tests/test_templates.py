"""Contract tests for pluggable log-template parsers."""

from __future__ import annotations

import pytest

from logsight.templates import (
    BaselineTemplateParser,
    Drain3TemplateParser,
    build_template_parser,
)


class FakeDrain3Miner:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.messages: list[str] = []

    def add_log_message(self, log_message: str) -> dict[str, object]:
        self.messages.append(log_message)
        return self.result


def test_baseline_parser_preserves_existing_template_contract() -> None:
    parser = BaselineTemplateParser()

    assert parser.parse("request 42 failed from 10.1.2.3") == "request <*> failed from <*>"


def test_drain3_adapter_returns_mined_template() -> None:
    miner = FakeDrain3Miner({"template_mined": "request <*> failed"})
    parser = Drain3TemplateParser(template_miner=miner)

    assert parser.parse("request 42 failed") == "request <*> failed"
    assert miner.messages == ["request 42 failed"]


def test_drain3_adapter_rejects_invalid_miner_results() -> None:
    parser = Drain3TemplateParser(template_miner=FakeDrain3Miner({}))

    with pytest.raises(RuntimeError, match="usable template"):
        parser.parse("request failed")


def test_parser_factory_defaults_to_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGSIGHT_TEMPLATE_PARSER", raising=False)

    assert isinstance(build_template_parser(), BaselineTemplateParser)


def test_parser_factory_rejects_unknown_backends() -> None:
    with pytest.raises(ValueError, match="baseline.*drain3"):
        build_template_parser("unsupported")
