"""Contract tests for bounded distributed inference dispatch."""

from __future__ import annotations

import pytest

from logsight.distributed import CeleryInferenceDispatcher, InferenceRequest
from logsight.enterprise import enrich
from logsight.parser import parse_line


class FakeResult:
    id = "task-123"


class FakeCelery:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object], str]] = []

    def send_task(self, name: str, args: list[object], *, queue: str) -> FakeResult:
        self.calls.append((name, args, queue))
        return FakeResult()


def event(message: str):
    return enrich(parse_line(message), service="payments")


def test_dispatcher_queues_bounded_json_embedding_payloads() -> None:
    app = FakeCelery()
    dispatcher = CeleryInferenceDispatcher(app, queue="gpu", max_batch_size=2)

    task_id = dispatcher.submit_embeddings([event("ERROR database timeout")])

    assert task_id == "task-123"
    name, args, queue = app.calls[0]
    assert name == "logsight.embed_events"
    assert queue == "gpu"
    payload = args[0][0]
    assert payload["message"] == "database timeout"
    assert payload["fingerprint"]


def test_dispatcher_rejects_invalid_batches_before_enqueueing() -> None:
    app = FakeCelery()
    dispatcher = CeleryInferenceDispatcher(app, max_batch_size=1)

    with pytest.raises(ValueError, match="batch size"):
        dispatcher.submit_embeddings([event("INFO one"), event("INFO two")])

    assert app.calls == []


def test_request_rejects_payload_shape_and_oversized_message() -> None:
    with pytest.raises(ValueError, match="unexpected shape"):
        InferenceRequest.from_payload({}, max_message_chars=10)

    with pytest.raises(ValueError, match="within"):
        InferenceRequest(fingerprint="event", message="too long").validated(max_message_chars=3)
