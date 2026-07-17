# Production Readiness Audit

Date: 2026-07-17

## Executive summary

LogSight-AI has a small, understandable core parser/analyzer with streaming file reads, typed data structures, a CLI, tests, and a non-root container. The repository was not production-ready at audit start: CI targeted a nonexistent package, several checks suppressed failures, claimed metrics were not reproducible, deployment files described incompatible services, and input constraints were unenforced.

This hardening pass makes quality, coverage, security, packaging, and benchmark checks deterministic. The local statistical engine is the supported production scope. The Streamlit/Anthropic files remain prototypes and are intentionally excluded from the packaged runtime until their dependency, privacy, timeout, retry, and service contracts are designed.

## Strengths

- Dependency-light local analysis with no network requirement.
- Line-by-line file ingestion bounds memory use.
- Clear parser, analyzer, and CLI module boundaries.
- Error/critical classification and duplicate suppression are tested.
- Multi-stage, non-root OCI image.

## Risks and technical debt

| Priority | Risk | Impact | Treatment |
|---|---|---|---|
| P0 | CI failures were swallowed and coverage targeted `src` | False-green releases | Replaced with one fail-closed CI workflow and 90% gate |
| P0 | Invalid window/threshold inputs | Runtime crash or invalid results | Validate library and CLI boundaries |
| P1 | Prototype agent accepts sensitive logs and calls a third party | Privacy, availability, cost | Keep outside packaged runtime; add threat guidance |
| P1 | Dependencies were duplicated and loosely bounded | Drift and supply-chain exposure | Make `pyproject.toml` canonical; audit in CI |
| P1 | Compose advertised an API that does not exist | Deployment failure | Remove from supported deployment path; validate CLI container |
| P2 | Length z-score is a heuristic, not an ML accuracy model | False positives/negatives | Document limits; require labeled corpus before accuracy claims |
| P2 | No persistent service, auth, rate limit, or telemetry backend | Not horizontally scalable as an API | Add only with an explicit service SLO and threat model |

## Architecture and scalability

The supported data path is `file/stdin -> parser -> statistical analyzer -> CLI report`. Time is O(n), parsing is streaming for files, and analysis retains entries in memory, so CLI callers should partition very large inputs. There is no production network API or database to scale. Horizontal-service claims would therefore be misleading.

## Prioritized roadmap

1. Publish reproducible CI and benchmark artifacts from the default branch.
2. Pin released dependency versions with an automated lock/update policy.
3. Build a labeled, versioned evaluation corpus before reporting precision, recall, F1, ROC-AUC, MAP, MRR, or NDCG.
4. If an API is required, write an ADR covering authentication, authorization, rate limiting, request size, timeouts, observability, and data retention before implementation.
5. Add signed images, provenance attestations, staged deployment, monitoring, and rollback exercises before production rollout.

## Acceptance criteria

- Ruff, mypy, pytest, 90% coverage, package build, pip-audit, Bandit, CodeQL, secret scan, and SBOM jobs pass without `continue-on-error` or shell fallbacks.
- Benchmark JSON is retained and compared in pull requests.
- Container runs as non-root and `logsight health` succeeds.
- Documentation contains no fabricated performance or accuracy values.
