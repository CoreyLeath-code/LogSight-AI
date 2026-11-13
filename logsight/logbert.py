"""Optional LogBERT-compatible masked-language-model anomaly adapter."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from .enterprise import EnrichedLog


class TemplateLossBackend(Protocol):
    """Score normalized log templates; higher loss indicates less familiar text."""

    def score(self, templates: Sequence[str]) -> list[float]:
        """Return one non-negative masked-language-model loss per template."""


class TransformersMaskedLMBackend:
    """Lazy CPU adapter for a local Hugging Face masked-LM LogBERT checkpoint."""

    def __init__(self, model_path: str | Path, max_tokens: int = 256) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self.model_path = Path(model_path)
        self.max_tokens = max_tokens
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._lock = Lock()

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer
        if not self.model_path.is_dir():
            raise FileNotFoundError(f"LogBERT model directory was not found: {self.model_path}")
        try:
            from transformers import AutoModelForMaskedLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the ai extra to enable the LogBERT adapter") from exc
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            local_files_only=True,
            revision="local",  # nosec B615 - local_files_only uses a provisioned directory
        )
        self._model = AutoModelForMaskedLM.from_pretrained(
            self.model_path,
            local_files_only=True,
            revision="local",
        )
        self._model.eval()
        return self._model, self._tokenizer

    def score(self, templates: Sequence[str]) -> list[float]:
        if not templates:
            return []
        with self._lock:
            model, tokenizer = self._load()
            try:
                import torch
            except ImportError as exc:
                raise RuntimeError("Install the ai extra to enable the LogBERT adapter") from exc

            scores: list[float] = []
            for template in templates:
                encoded = tokenizer(
                    template,
                    truncation=True,
                    max_length=self.max_tokens,
                    return_tensors="pt",
                )
                labels = encoded["input_ids"].clone()
                with torch.no_grad():
                    output = model(**encoded, labels=labels)
                scores.append(float(output.loss.item()))
        return scores


@dataclass(frozen=True, slots=True)
class LogBertAssessment:
    """Per-event model score with an explicit threshold decision."""

    fingerprint: str
    model: str
    loss: float
    anomalous: bool


class LogBertAnomalyAdapter:
    """Bounded adapter that applies a calibrated loss threshold to templates."""

    def __init__(
        self,
        backend: TemplateLossBackend,
        *,
        model_name: str,
        loss_threshold: float,
        max_batch_size: int = 64,
        max_template_chars: int = 16_000,
    ) -> None:
        if not math.isfinite(loss_threshold) or loss_threshold <= 0:
            raise ValueError("loss_threshold must be a positive finite value")
        if max_batch_size < 1 or max_template_chars < 1:
            raise ValueError("LogBERT adapter limits must be positive")
        self.backend = backend
        self.model_name = model_name
        self.loss_threshold = loss_threshold
        self.max_batch_size = max_batch_size
        self.max_template_chars = max_template_chars

    def assess(self, events: Sequence[EnrichedLog]) -> list[LogBertAssessment]:
        """Score one bounded event batch without changing ingest-path semantics."""

        if not 1 <= len(events) <= self.max_batch_size:
            raise ValueError(f"batch size must be between 1 and {self.max_batch_size}")
        templates = [event.template or event.message for event in events]
        if any(not template or len(template) > self.max_template_chars for template in templates):
            raise ValueError("event templates must be non-empty and within the configured limit")

        losses = self.backend.score(templates)
        if len(losses) != len(events):
            raise RuntimeError("LogBERT backend returned an unexpected score count")
        if any(not math.isfinite(loss) or loss < 0 for loss in losses):
            raise RuntimeError("LogBERT backend returned an invalid loss")

        return [
            LogBertAssessment(
                fingerprint=event.fingerprint or "",
                model=self.model_name,
                loss=loss,
                anomalous=loss >= self.loss_threshold,
            )
            for event, loss in zip(events, losses)
        ]


def build_logbert_adapter(
    *,
    model_path: str | Path | None = None,
    loss_threshold: float | None = None,
    max_batch_size: int | None = None,
) -> LogBertAnomalyAdapter:
    """Build a local-checkpoint adapter from explicit values or environment."""

    resolved_path = model_path or os.getenv("LOGSIGHT_LOGBERT_MODEL_PATH")
    if not resolved_path:
        raise ValueError("LOGSIGHT_LOGBERT_MODEL_PATH must be configured")
    resolved_threshold = (
        loss_threshold
        if loss_threshold is not None
        else float(os.getenv("LOGSIGHT_LOGBERT_LOSS_THRESHOLD", "0"))
    )
    resolved_batch_size = (
        max_batch_size
        if max_batch_size is not None
        else int(os.getenv("LOGSIGHT_LOGBERT_BATCH_SIZE", "64"))
    )
    return LogBertAnomalyAdapter(
        TransformersMaskedLMBackend(resolved_path),
        model_name=Path(resolved_path).name,
        loss_threshold=resolved_threshold,
        max_batch_size=resolved_batch_size,
    )
