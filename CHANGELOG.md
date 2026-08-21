# Changelog

All notable release-level changes to LogSight-AI are documented here.

## [Unreleased]

## [0.1.0] - 2026-08-21

### Added
- Installable `logsight-ai` Python package with the `logsight` console entry point.
- Automated quality checks covering formatting, linting, strict type checking, tests, and coverage.
- Package and Docker-image build verification in CI, including a container health command.
- Security checks including Bandit, dependency auditing, secret scanning, license inventory, and an SPDX SBOM artifact.
- Reproducible pytest-benchmark execution with JSON benchmark artifacts.
- Tagged release automation that builds Python distributions, publishes the LogSight-AI container to GHCR, and creates a GitHub Release.

### Release scope
- Version `0.1.0` remains an alpha release, matching the package metadata.
- This changelog describes repository capabilities already represented by the package and CI/release configuration; it does not claim production readiness or measured real-world capacity.
