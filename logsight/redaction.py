"""Conservative text redaction for the optional API ingest boundary.

These patterns reduce accidental disclosure, but cannot identify every secret or
personal datum. Deployments must classify data and enforce an approved policy.
"""

from __future__ import annotations

import re

_REPLACEMENT = "[REDACTED]"
_BEARER = re.compile(r"(?i)(\\bBearer\\s+)[A-Za-z0-9._~+/-]+={0,2}")
_ASSIGNMENT = re.compile(
    r"(?i)(\\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization)\\b\\s*[:=]\\s*)(?:\\\"[^\\\"]*\\\"|'[^']*'|[^\\s,;]+)"
)
_EMAIL = re.compile(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b")


def redact_log_line(line: str) -> str:
    """Return an API-safe copy; never retain or return the original input."""
    redacted = _BEARER.sub(lambda match: match.group(1) + _REPLACEMENT, line)
    redacted = _ASSIGNMENT.sub(lambda match: match.group(1) + _REPLACEMENT, redacted)
    return _EMAIL.sub(_REPLACEMENT, redacted)
