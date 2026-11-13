"""Contract tests for the bounded LogBERT anomaly adapter."""

from __future__ import annotations

import pytest

from logsight.enterprise import enrich
from logsight.logbert import LogBertAnomalyAdapter
from logsight.parser import parse_line


class FakeLossBackend:
    def __init__(self, losses: list[float]) -> None:
        self.losses = losses
        self.templates: list[str] = []

    def score(self, templates: list[str]) -> list[float]:
        self.templates = templates
        return self.losses


def event(message: str):
    enriched = enrich(parse_line(message), service="payments")
    enriched.template = "request <*> failed"
    return enriched


def test_adapter_scores_templates_with_explicit_threshold() -> None:
    backend = FakeLossBackend([0.4, 1.2])
    adapter = LogBertAnomalyAdapter(
        backend,
        model_name="logsight-logbert",
        loss_threshold=1.0,
        max_batch_size=2,
    )
    events = [event("ERROR request 42 failed"), event("ERROR request 99 failed")]

    assessments = adapter.assess(events)

    assert backend.templates == ["request <*> failed", "request <*> failed"]
    assert assessments[0].anomalous is False
    assert assessments[1].anomalous is True
    assert assessments[0].fingerprint == events[0].fingerprint


def test_adapter_rejects_invalid_input_and_backend_output() -> None:
    backend = FakeLossBackend([float("nan")])
    adapter = LogBertAnomalyAdapter(backend, model_name="test", loss_threshold=1.0)

    with pytest.raises(RuntimeError, match="invalid loss"):
        adapter.assess([event("ERROR request failed")])

    with pytest.raises(ValueError, match="batch size"):
        adapter.assess([])


def test_adapter_rejects_unexpected_score_count() -> None:
    adapter = LogBertAnomalyAdapter(
        FakeLossBackend([0.1]), model_name="test", loss_threshold=1.0
    )

    with pytest.raises(RuntimeError, match="unexpected score count"):
        adapter.assess([event("INFO one"), event("INFO two")])
