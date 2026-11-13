"""Bounded optional ONNX Runtime inference worker for normalized log features."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from .enterprise import EnrichedLog


class InferenceBackend(Protocol):
    """Model runtime contract used by the bounded worker."""

    def infer(self, rows: Sequence[Sequence[float]]) -> list[list[float]]:
        """Return one score vector for each feature row."""


class _OnnxInput(Protocol):
    name: str


class _OnnxSession(Protocol):
    def get_inputs(self) -> list[_OnnxInput]:
        """Return declared input metadata."""

    def run(self, output_names: None, input_feed: dict[str, Any]) -> list[Any]:
        """Run inference and return model outputs."""


class OnnxRuntimeBackend:
    """CPU ONNX Runtime adapter with a single-input, first-output contract."""

    def __init__(self, model_path: str | Path, session: _OnnxSession | None = None) -> None:
        self.model_path = Path(model_path)
        self._session = session or self._create_session(self.model_path)
        inputs = self._session.get_inputs()
        if len(inputs) != 1:
            raise ValueError("ONNX inference requires exactly one model input")
        self._input_name = inputs[0].name

    @staticmethod
    def _create_session(model_path: Path) -> _OnnxSession:
        if not model_path.is_file():
            raise FileNotFoundError(f"ONNX model was not found: {model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("Install the ai extra to enable ONNX Runtime inference") from exc
        return cast(
            _OnnxSession,
            ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"]),
        )

    def infer(self, rows: Sequence[Sequence[float]]) -> list[list[float]]:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Install the ai extra to enable ONNX Runtime inference") from exc
        array = np.asarray(rows, dtype=np.float32)
        outputs = self._session.run(None, {self._input_name: array})
        if not outputs:
            raise RuntimeError("ONNX model returned no outputs")
        values = outputs[0].tolist()
        if not isinstance(values, list):
            raise RuntimeError("ONNX model returned an unsupported output shape")
        if values and not isinstance(values[0], list):
            values = [[float(value)] for value in values]
        return [[float(value) for value in row] for row in values]


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Model score vector associated with the normalized event identity."""

    fingerprint: str
    model: str
    scores: tuple[float, ...]


class OnnxInferenceWorker:
    """Validate bounded feature batches before invoking an inference runtime."""

    def __init__(
        self,
        backend: InferenceBackend,
        *,
        model_name: str,
        feature_dimension: int,
        max_batch_size: int = 64,
    ) -> None:
        if feature_dimension < 1 or max_batch_size < 1:
            raise ValueError("inference worker limits must be positive")
        self.backend = backend
        self.model_name = model_name
        self.feature_dimension = feature_dimension
        self.max_batch_size = max_batch_size

    def infer(
        self, events: Sequence[EnrichedLog], features: Sequence[Sequence[float]]
    ) -> list[InferenceResult]:
        """Infer scores for a bounded, aligned batch of events and features."""

        if not 1 <= len(events) <= self.max_batch_size:
            raise ValueError(f"batch size must be between 1 and {self.max_batch_size}")
        if len(features) != len(events):
            raise ValueError("events and feature rows must have the same length")
        if any(
            len(row) != self.feature_dimension
            or not all(math.isfinite(value) for value in row)
            for row in features
        ):
            raise ValueError("feature rows must be finite and match the configured dimension")

        scores = self.backend.infer(features)
        if len(scores) != len(events):
            raise RuntimeError("inference backend returned an unexpected score count")

        result_dimension: int | None = None
        results: list[InferenceResult] = []
        for event, score in zip(events, scores):
            if not score or not all(math.isfinite(value) for value in score):
                raise RuntimeError("inference backend returned invalid scores")
            if result_dimension is None:
                result_dimension = len(score)
            elif len(score) != result_dimension:
                raise RuntimeError("inference backend returned inconsistent score dimensions")
            results.append(
                InferenceResult(
                    fingerprint=event.fingerprint or "",
                    model=self.model_name,
                    scores=tuple(score),
                )
            )
        return results


def build_onnx_worker(
    *,
    model_path: str | Path | None = None,
    feature_dimension: int | None = None,
    max_batch_size: int | None = None,
) -> OnnxInferenceWorker:
    """Build a configured worker; model location and input shape are required."""

    resolved_path = model_path or os.getenv("LOGSIGHT_ONNX_MODEL_PATH")
    if not resolved_path:
        raise ValueError("LOGSIGHT_ONNX_MODEL_PATH must be configured")
    resolved_dimension = (
        feature_dimension
        if feature_dimension is not None
        else int(os.getenv("LOGSIGHT_ONNX_INPUT_DIMENSION", "0"))
    )
    resolved_batch_size = (
        max_batch_size
        if max_batch_size is not None
        else int(os.getenv("LOGSIGHT_ONNX_BATCH_SIZE", "64"))
    )
    return OnnxInferenceWorker(
        OnnxRuntimeBackend(resolved_path),
        model_name=Path(resolved_path).name,
        feature_dimension=resolved_dimension,
        max_batch_size=resolved_batch_size,
    )
