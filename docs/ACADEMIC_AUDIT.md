# Academic Audit: LogSight-AI

## Scope and evidence standard

LogSight-AI is a local-first log-analysis CLI. This audit distinguishes **MEASURED** claims backed by a versioned benchmark report, **DERIVED** claims that follow from source, and **OBSERVED** repository properties. It is not a trained incident-classification system and has no labeled accuracy evaluation.

## Evidence currently present

| Dimension | Assessment | Evidence |
|---|---|---|
| Direct algorithmic work | **DERIVED** | `logsight/analyzer.py` implements message-length z-score detection, error-level flags, frequency summaries, and windowed error-rate spikes directly. |
| Input representation | **OBSERVED** | `logsight/parser.py` maps local stdin/files into typed `LogEntry` records across four documented formats. |
| Mathematical correctness tests | **OBSERVED** | `tests/test_analyzer.py` checks counts, threshold validation, z-score outliers, duplicate suppression, and exact spike-window evidence. |
| Performance evidence | **MEASURED** | `benchmarks/benchmark_report.md` records a local 1,000-line baseline from 2026-07-17; CI uploads per-commit raw benchmark JSON. |
| Security and delivery | **OBSERVED** | CI runs linting, type checking, tests, package/container checks, Bandit, dependency audit, secret scan, SBOM, and benchmark artifact upload. |
| Model accuracy | **NOT MEASURED** | No labeled incident corpus, ground-truth annotation protocol, baseline comparison, or precision/recall result is committed. |

## Strengths for an academic reviewer

1. The anomaly logic is inspectable: each result can cite an error-level predicate, a z-score, or an observed window error rate.
2. The system is local-first and explicitly avoids transmitting logs or implying an LLM-derived root cause.
3. The detector has an evidence type (`AnomalyEvidence` and `ErrorRateSpike`) rather than only an opaque boolean.
4. Benchmark methodology correctly distinguishes a CLI microbenchmark from an end-to-end service load test.

## Gaps and threats to validity

| Gap | Why it matters |
|---|---|
| No labeled corpus spanning formats, services, and incident types | Detection quality, false positives, and false negatives cannot be estimated. |
| Fixed z-score and rate thresholds | The defaults (2.5 and 0.25) are policy values, not calibrated significance levels. |
| Message length is a narrow feature | Short but harmful messages and long benign messages can be misclassified. |
| Windows are non-overlapping and incomplete tails are ignored | Spikes straddling a window boundary or the final partial window may be missed. |
| Parse format and severity depend on regular-expression matching | Unrecognized or vendor-specific lines can reduce signal quality. |
| A test for `flag_errors=False` is non-assertive | It does not establish the intended behavior and should be strengthened before relying on that option. |

## Research questions enabled by future work

1. What precision, recall, and alert burden result from z-score, error-rate, and error-level rules on a versioned labeled corpus?
2. How do overlapping, time-based, and non-overlapping windows trade detection delay against false alerts?
3. How stable are thresholds across log formats, services, and message-length distributions?
4. Does a simple baseline such as error-level-only detection outperform or complement the z-score rule?
5. How does parsing and analysis latency scale with line count, line length, format mix, and unique-message cardinality?

## Claims policy

Appropriate wording is “explainable statistical heuristic,” “local CLI,” “measured 1,000-line development baseline,” and “per-commit benchmark artifact.” Do not claim learned anomaly detection, incident-root-cause identification, production readiness, accuracy, or hardware-independent throughput without the required evidence.
