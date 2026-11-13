"""Contract tests for bounded ONNX inference worker behavior."""

from __future__ import annotations

import pytest

from logsight.enterprise import enrich
from logsight.onnx_worker import OnnxInferenceWorker
from logsight.parser import parse_line


class FakeBackend:
    def __init__(self, scores: list[list[float]]) -> None:
        self.scores = scores
        self.rows: list[list[float]] = []

    def infer(self, rows: list[list[float]]) -> list[list[float]]:
        self.rows = rows
        return self.scores


def event(message: str):
    return enrich(parse_line(message), service="payments")


def test_worker_infers_aligned_bounded_feature_batches() -> None:
    backend = FakeBackend([[0.2, 0.8], [0.7, 0.3]])
    worker = OnnxInferenceWorker(
        backend, model_name="detector.onnx", feature_dimension=3, max_batch_size=2
    )
    events = [event("ERROR timeout"), event("INFO completed")]

    results = worker.infer(events, [[1.0, 0.0, 0.5], [0.0, 1.0, 0.5]])

    assert backend.rows == [[1.0, 0.0, 0.5], [0.0, 1.0, 0.5]]
    assert results[0].fingerprint == events[0].fingerprint
    assert results[0].model == "detector.onnx"
    assert results[1].scores == (0.7, 0.3)


def test_worker_rejects_misaligned_or_non_finite_features() -> None:
    backend = FakeBackend([[1.0]])
    worker = OnnxInferenceWorker(backend, model_name="test", feature_dimension=2)

    with pytest.raises(ValueError, match="same length"):
        worker.infer([event("INFO one")], [])
    with pytest.raises(ValueError, match="finite"):
        worker.infer([event("INFO one")], [[float("nan"), 1.0]])

    assert backend.rows == []


def test_worker_rejects_malformed_backend_scores() -> None:
    worker = OnnxInferenceWorker(
        FakeBackend([[0.1], [0.2, 0.8]]), model_name="test", feature_dimension=1
    )

    with pytest.raises(RuntimeError, match="inconsistent"):
        worker.infer([event("INFO one"), event("INFO two")], [[1.0], [2.0]])
