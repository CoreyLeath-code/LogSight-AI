# LogSight-AI

[![CI](https://github.com/CoreyLeath-code/LogSight-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/CoreyLeath-code/LogSight-AI/actions/workflows/ci.yml)
[![CodeQL](https://github.com/CoreyLeath-code/LogSight-AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/CoreyLeath-code/LogSight-AI/actions/workflows/codeql.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

LogSight-AI is a local-first Python CLI for parsing common log formats, summarizing error patterns, detecting message-length outliers, and locating error-rate spikes. The production package does not transmit logs or require credentials.


LogSight-AI parses local log files and standard input into typed events, summaries, outlier findings, and error-rate spike reports. It does not operate a hosted service, persist logs, or claim learned incident-detection accuracy. A production deployment would require a supported service boundary, authenticated multi-user access, retention and redaction controls, observability, and an owned deployment and rollback path.

## Architecture flowchart

```mermaid
flowchart LR
    Input --> Validate[Schema + data checks] --> Model[Versioned model] --> Serve[API / dashboard] --> Observe[Metrics + drift]
```

### Quickstart and local validation

The supported local path should be reproducible from a clean checkout. The inferred stack for this repository is **Python/ML**.

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest -q
```

If the project uses external services, model artifacts, cloud credentials, or private data, start them through documented local fixtures or mocks. Never place secrets or identifiable records in the repository.

### Research-style metrics and benchmarks

| Evidence | Required record |
|---|---|
| Correctness | Test command, commit SHA, runtime, and pass/fail result |
| Performance | Warm-up, sample count, concurrency, median, p95, p99, throughput, and memory |
| Data/model quality | Dataset version, split strategy, leakage controls, calibration, subgroup results, and uncertainty |
| Runtime | Image digest, health-check latency, resource limits, and rollback target |
| Security | Dependency, secret, SAST, container, and SBOM results |

A benchmark number belongs in a versioned artifact tied to a commit and hardware/runtime description. Engineering benchmarks must not be presented as clinical, financial, safety, or model-quality validation without the appropriate domain evidence.

### Extended Q&A

**What is production-ready for this repository?**  
A reproducible build, tested public contract, controlled configuration, observable runtime, documented security boundary, versioned artifacts, and a tested rollback path.

**What must remain explicit?**  
The intended use, excluded use, data/credential handling, model or algorithm limitations, and which metrics are measured versus aspirational.

**What should be completed next?**  
Use the linked production-readiness issue for this repository as the checklist. Resolve missing tests, deployment instructions, observability, supply-chain controls, and release evidence before attaching a production claim.


## Architecture

```mermaid
flowchart LR
    A["File or stdin"] --> B["Format parser"]
    B --> C["Typed LogEntry records"]
    C --> D["Statistics and anomaly analysis"]
    D --> E["Rich CLI report"]
```

Supported formats include ISO-8601 application logs, syslog, nginx access logs, and generic level-prefixed lines. Detection is an explainable statistical heuristic; it is not a trained model and no accuracy claim is made without a labeled evaluation corpus.

## Evidence-backed reasoning

The optional `--explain` flag turns existing detector output into concise, user-facing evidence statements. Each statement identifies its direct or statistical basis: parsed error level, message-length z-score with its configured threshold, or observed error count/rate in a complete analysis window. Each statement also reports a deterministic support level: `single-signal` for one detector signal and `corroborated` when the same entry meets both error-level and statistical criteria. LogSight does not infer an incident root cause, use an LLM, send logs externally, or report a model-confidence score.

```bash
logsight analyze application.log --window 200 --spike-threshold 0.20 --explain
cat application.log | logsight stdin --explain
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
logsight health
logsight analyze application.log
cat application.log | logsight stdin
```

Useful controls:

```bash
logsight analyze application.log --threshold 3.0 --window 200 --spike-threshold 0.20
```

## Verified metrics

Measured locally on 2026-07-17; CI artifacts are the canonical per-commit record.

| Metric | Value |
|---|---:|
| Automated tests | 50 passing |
| Core package coverage | 95.26% |
| Benchmark input | 1,000 lines |
| Median pipeline latency | 10.315 ms |
| Mean throughput | 96.21 runs/sec |
| Approximate line throughput | 96,213 lines/sec |
| Security findings | Pending CI security job |
| Docker image size | Pending CI build |

Results vary by hardware and Python version. See [Benchmark Guide](docs/BENCHMARKING.md) and [Benchmark Report](benchmarks/benchmark_report.md).

## Engineering controls

Every pull request runs formatting, linting, strict type checking, unit/integration/CLI tests, a 90% coverage gate, package and container validation, Bandit, dependency audit, SBOM generation, CodeQL, and a reproducible microbenchmark. Checks fail closed.

## Documentation

- [Production audit](docs/AUDIT.md)
- [Architecture](docs/architecture.md)
- [Deployment and rollback checklist](docs/DEPLOYMENT.md)
- [Benchmark methodology](docs/BENCHMARKING.md)
- [Runtime metrics](docs/metrics.md)
- [Security policy](SECURITY.md)

The Streamlit and external-LLM files are retained as demonstrations and are not part of the supported package or deployment contract; see the audit for the work required to promote them.

## Development

```bash
pip install -e ".[dev]"
ruff format .
ruff check .
mypy
pytest
```

Contributions should include tests and documentation for behavioral changes. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
