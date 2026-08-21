# LogSight-AI v0.1.0

LogSight-AI v0.1.0 is the first versioned release prepared from the repository's existing installable Python package and verified CI surface.

## Verified release surface

The repository declares package version `0.1.0`, Python `>=3.10`, and a `logsight` console entry point in `pyproject.toml`.

The existing CI verifies:

- formatting with Ruff;
- linting with Ruff;
- strict mypy checks for the `logsight` package;
- pytest with a 90% coverage floor;
- Python package builds;
- Docker image builds and the container `health` command;
- Bandit, pip-audit, Gitleaks, license inventory, and SPDX SBOM generation;
- a pytest-benchmark run with a JSON artifact.

## Publishing contract

The release workflow added for v0.1.0 triggers only on semantic-version tags matching `v*.*.*`. It verifies that the pushed tag matches the package version before publishing.

For `v0.1.0`, a successful tagged workflow will:

1. build the wheel and source distribution in `dist/`;
2. publish a container to `ghcr.io/CoreyLeath-code/logsight-ai` with semantic-version and `latest` tags;
3. create the GitHub Release with generated release notes; and
4. attach the built Python distributions to the GitHub Release.

## Scope

This is an alpha release. The release does not claim production readiness, horizontal scalability, or real-world capacity/performance beyond evidence explicitly stored and reproducible in the repository.
