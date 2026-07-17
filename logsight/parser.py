"""Log line parser supporting common log formats."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


# Ordered from most- to least-specific so the first match wins.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "syslog",
        re.compile(
            r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
            r"(?P<host>\S+)\s+(?P<process>\S+):\s+(?P<message>.+)$"
        ),
    ),
    (
        "iso8601",
        re.compile(
            r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
            r"\s+(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)?\s*"
            r"(?:\[(?P<logger>[^\]]+)\])?\s*(?P<message>.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "nginx_access",
        re.compile(
            r"^(?P<host>\S+)\s+-\s+(?P<user>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+"
            r'"(?P<request>[^"]+)"\s+(?P<status>\d{3})\s+(?P<bytes>\d+)'
        ),
    ),
    (
        "generic",
        re.compile(
            r"^(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)?\s*(?P<message>.+)$",
            re.IGNORECASE,
        ),
    ),
]

# Timestamp formats tried in order when parsing iso8601-style strings.
_TS_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
]

_LEVEL_ALIASES: dict[str, LogLevel] = {
    "WARN": LogLevel.WARNING,
    "FATAL": LogLevel.CRITICAL,
}


def _parse_level(raw: str | None) -> LogLevel:
    if not raw:
        return LogLevel.UNKNOWN
    key = raw.upper()
    if key in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[key]
    try:
        return LogLevel(key)
    except ValueError:
        return LogLevel.UNKNOWN


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip().replace(",", ".")
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


@dataclass
class LogEntry:
    """A single parsed log line."""

    raw: str
    format: str = "unknown"
    timestamp: datetime | None = None
    level: LogLevel = LogLevel.UNKNOWN
    message: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.level in (LogLevel.ERROR, LogLevel.CRITICAL)


def parse_line(line: str) -> LogEntry:
    """Parse a single log line and return a :class:`LogEntry`."""
    line = line.rstrip("\n\r")
    for fmt_name, pattern in _PATTERNS:
        m = pattern.match(line)
        if m:
            groups = m.groupdict()
            entry = LogEntry(raw=line, format=fmt_name)
            entry.timestamp = _parse_timestamp(groups.get("timestamp"))
            entry.level = _parse_level(groups.get("level"))
            entry.message = groups.get("message") or line
            # Stash any remaining named groups as extras.
            skip = {"timestamp", "level", "message"}
            entry.extra = {k: v for k, v in groups.items() if k not in skip and v is not None}
            return entry
    return LogEntry(raw=line, message=line)


def parse_lines(lines: Iterable[str]) -> list[LogEntry]:
    """Parse an iterable of log lines, excluding blank records."""
    return [parse_line(line) for line in lines if line.strip()]


def parse_file(path: str) -> Iterator[LogEntry]:
    """Yield :class:`LogEntry` objects from *path* line by line."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                yield parse_line(line)
