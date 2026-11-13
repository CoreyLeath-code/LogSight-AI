"""Bounded optional embedding worker for normalized log events."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

from .enterprise import EnrichedLog

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingBackend(Protocol):
    """Minimal model contract shared by Sentence-Transformers and adapters."""

    def encode(self, messages: Sequence[str]) -> list[list[float]]:
        """Return one normalized vector for each input message."""


class SentenceTransformerBackend:
    """Lazy Sentence-Transformers backend with serialized model invocation."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model: Any | None = None
        self._lock = Lock()

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Install the ai extra to enable Sentence-Transformers embeddings"
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, messages: Sequence[str]) -> list[list[float]]:
        if not messages:
            return []
        with self._lock:
            vectors = self._load().encode(
                list(messages),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return [[float(value) for value in vector] for vector in vectors]


@dataclass(frozen=True, slots=True)
class EmbeddedLog:
    """Embedding result that retains event identity and model provenance."""

    fingerprint: str
    model: str
    vector: tuple[float, ...]


class EmbeddingWorker:
    """Bounded batch worker that keeps model inference off the ingest request path."""

    def __init__(
        self,
        backend: EmbeddingBackend,
        *,
        model_name: str,
        max_batch_size: int = 64,
        max_message_chars: int = 16_000,
    ) -> None:
        if max_batch_size < 1 or max_message_chars < 1:
            raise ValueError("embedding worker limits must be positive")
        self.backend = backend
        self.model_name = model_name
        self.max_batch_size = max_batch_size
        self.max_message_chars = max_message_chars

    def embed(self, events: Sequence[EnrichedLog]) -> list[EmbeddedLog]:
        """Embed one bounded batch, rejecting malformed model output."""

        if not 1 <= len(events) <= self.max_batch_size:
            raise ValueError(f"batch size must be between 1 and {self.max_batch_size}")
        messages = [event.message for event in events]
        if any(not message or len(message) > self.max_message_chars for message in messages):
            raise ValueError("event messages must be non-empty and within the configured limit")

        vectors = self.backend.encode(messages)
        if len(vectors) != len(events):
            raise RuntimeError("embedding backend returned an unexpected vector count")

        dimension: int | None = None
        results: list[EmbeddedLog] = []
        for event, vector in zip(events, vectors):
            if not vector or not all(math.isfinite(value) for value in vector):
                raise RuntimeError("embedding backend returned an invalid vector")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise RuntimeError("embedding backend returned inconsistent vector dimensions")
            results.append(
                EmbeddedLog(
                    fingerprint=event.fingerprint or "",
                    model=self.model_name,
                    vector=tuple(vector),
                )
            )
        return results


def build_embedding_worker(
    *,
    model_name: str | None = None,
    max_batch_size: int | None = None,
) -> EmbeddingWorker:
    """Build the optional worker from explicit values or deployment settings."""

    resolved_model = model_name or os.getenv("LOGSIGHT_EMBEDDING_MODEL", DEFAULT_MODEL)
    resolved_batch_size = max_batch_size or int(os.getenv("LOGSIGHT_EMBEDDING_BATCH_SIZE", "64"))
    return EmbeddingWorker(
        SentenceTransformerBackend(resolved_model),
        model_name=resolved_model,
        max_batch_size=resolved_batch_size,
    )
