# Benchmark Guide

Run `pytest tests/test_benchmarks.py --benchmark-only --benchmark-json=benchmarks/latest.json`. The JSON includes distribution statistics such as min, max, mean, median, standard deviation, rounds, and operations per second. CI retains it as an artifact.

Compare two runs with `pytest-benchmark compare benchmarks/baseline.json benchmarks/latest.json`. Use the same Python version, hardware class, power profile, input size, and warm-up settings. A microbenchmark is not an end-to-end service load test; user-concurrency, GPU, model-quality, and network metrics are not applicable to the current local CLI architecture.

## Detection-quality benchmark

The performance benchmark above measures runtime only. For labeled detection quality and alert
burden, run `logsight benchmark` against the versioned synthetic corpus. See
[Labeled benchmark corpus](LABELED_BENCHMARKS.md) for labels, metric definitions, and
promotion-gate guidance.
