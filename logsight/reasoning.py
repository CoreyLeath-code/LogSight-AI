"""Evidence-backed explanations for deterministic LogSight findings.

This module does not infer a root cause or use a language model.  Each explanation
is derived only from the detector's recorded reason, threshold, and observed value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from logsight.analyzer import AnomalyReport, ErrorRateSpike

EvidenceStrength = Literal["direct", "statistical"]
SupportLevel = Literal["single-signal", "corroborated"]


@dataclass(frozen=True)
class EvidenceExplanation:
    """Concise user-facing explanation with machine-readable evidence strings."""

    category: str
    summary: str
    evidence_strength: EvidenceStrength
    support_level: SupportLevel
    evidence: tuple[str, ...]


def explain_report(
    report: AnomalyReport,
    spikes: list[ErrorRateSpike] | None = None,
) -> list[EvidenceExplanation]:
    """Explain detector output without claiming a cause beyond observed evidence."""

    explanations: list[EvidenceExplanation] = []
    for finding in report.evidence:
        entry = finding.entry
        if "error_level" in finding.reasons:
            explanations.append(
                EvidenceExplanation(
                    category="error-level",
                    summary=(
                        f"Entry was flagged because its parsed level is {entry.level.value}; "
                        "no root cause is inferred."
                    ),
                    evidence_strength="direct",
                    support_level=(
                        "corroborated"
                        if "message_length_zscore" in finding.reasons
                        else "single-signal"
                    ),
                    evidence=(
                        f"level={entry.level.value}",
                        f"message_length={len(entry.message)}",
                    ),
                )
            )
        if "message_length_zscore" in finding.reasons and finding.message_length_zscore is not None:
            explanations.append(
                EvidenceExplanation(
                    category="message-length-outlier",
                    summary=(
                        "Entry was flagged because its message length exceeded the configured "
                        "statistical threshold; no root cause is inferred."
                    ),
                    evidence_strength="statistical",
                    support_level=(
                        "corroborated" if "error_level" in finding.reasons else "single-signal"
                    ),
                    evidence=(
                        f"zscore={finding.message_length_zscore:.3f}",
                        f"threshold={report.zscore_threshold:.3f}",
                        f"message_length={len(entry.message)}",
                    ),
                )
            )

    for spike in spikes or []:
        explanations.append(
            EvidenceExplanation(
                category="error-rate-spike",
                summary=(
                    f"Entries {spike.start}-{spike.end} crossed the configured error-rate "
                    "threshold; no root cause is inferred."
                ),
                evidence_strength="statistical",
                support_level="single-signal",
                evidence=(
                    f"errors={spike.error_count}",
                    f"entries={spike.total}",
                    f"error_rate={spike.error_rate:.3f}",
                    f"threshold={spike.threshold:.3f}",
                ),
            )
        )
    return explanations
