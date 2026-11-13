"""Contract tests for the bounded embedding worker."""

from __future__ import annotations

import pytest

from logsight.embeddings import EmbeddingWorker
from logsight.enterprise import enrich
from logsight.parser import parse_line


class FakeBackend:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.messages: list[str] = []

    def encode(self, messages: list[str]) -> list[list[float]]:
        self.messages = messages
        return self.vectors


def event(message: str):
    return enrich(parse_line(message), service="payments")


def test_worker_embeds_bounded_events_with_provenance() -> None:
    backend = FakeBackend([[0.6, 0.8], [1.0, 0.0]])
    worker = EmbeddingWorker(backend, model_name="test-model", max_batch_size=2)
    events = [event("ERROR database timeout"), event("INFO request completed")]

    results = worker.embed(events)

    assert backend.messages == ["database timeout", "request completed"]
    assert [result.model for result in results] == ["test-model", "test-model"]
    assert results[0].fingerprint == events[0].fingerprint
    assert results[0].vector == (0.6, 0.8)


def test_worker_rejects_oversized_batches_before_model_call() -> None:
    backend = FakeBackend([[1.0]])
    worker = EmbeddingWorker(backend, model_name="test-model", max_batch_size=1)

    with pytest.raises(ValueError, match="batch size"):
        worker.embed([event("INFO one"), event("INFO two")])

    assert backend.messages == []


def test_worker_rejects_bad_model_output() -> None:
    worker = EmbeddingWorker(FakeBackend([[1.0, float("nan")]]), model_name="test-model")

    with pytest.raises(RuntimeError, match="invalid vector"):
        worker.embed([event("ERROR timeout")])


def test_worker_rejects_inconsistent_dimensions() -> None:
    backend = FakeBackend([[1.0], [1.0, 0.0]])
    worker = EmbeddingWorker(backend, model_name="test-model")

    with pytest.raises(RuntimeError, match="inconsistent"):
        worker.embed([event("INFO one"), event("INFO two")])
