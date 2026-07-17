# Security Policy

## Supported versions

Security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's private vulnerability reporting for this repository. Include affected versions, reproduction steps, impact, and any suggested mitigation. Maintainers should acknowledge a report within three business days and provide a remediation timeline after triage.

## Security model

The core parser operates locally and does not require credentials. Treat log input as untrusted and potentially sensitive. Do not submit production logs to the optional LLM demonstration without an approved data-handling agreement. Secrets belong in environment variables or a secrets manager and must never be committed.

Supply-chain controls include dependency auditing, CodeQL, secret scanning, SBOM generation, least-privilege workflow permissions, and a non-root container user.
