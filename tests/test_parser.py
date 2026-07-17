"""Tests for logsight.parser."""

from __future__ import annotations

import textwrap

from logsight.parser import LogEntry, LogLevel, parse_line, parse_lines


class TestParseLevel:
    def test_known_levels(self):
        for line, expected in [
            ("INFO starting up", LogLevel.INFO),
            ("WARNING disk full", LogLevel.WARNING),
            ("ERROR connection refused", LogLevel.ERROR),
            ("CRITICAL out of memory", LogLevel.CRITICAL),
            ("DEBUG checkpoint reached", LogLevel.DEBUG),
        ]:
            entry = parse_line(line)
            assert entry.level == expected, f"Expected {expected} for {line!r}, got {entry.level}"

    def test_warn_alias(self):
        entry = parse_line("WARN this is a warning")
        assert entry.level == LogLevel.WARNING

    def test_fatal_alias(self):
        entry = parse_line("FATAL system crash")
        assert entry.level == LogLevel.CRITICAL

    def test_unknown_level(self):
        entry = parse_line("no level prefix here")
        assert entry.level == LogLevel.UNKNOWN


class TestIso8601Format:
    def test_invalid_timestamp_is_none(self):
        entry = parse_line("2024-99-99T99:99:99 INFO impossible")
        assert entry.timestamp is None

    def test_basic(self):
        line = "2024-01-15T12:34:56 INFO [app] Server started"
        entry = parse_line(line)
        assert entry.level == LogLevel.INFO
        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 15

    def test_space_separator(self):
        line = "2024-06-01 09:00:00 ERROR database timeout"
        entry = parse_line(line)
        assert entry.level == LogLevel.ERROR
        assert entry.timestamp is not None

    def test_milliseconds(self):
        line = "2024-03-20T08:15:30.123 WARNING slow query detected"
        entry = parse_line(line)
        assert entry.level == LogLevel.WARNING
        assert entry.timestamp is not None

    def test_format_label(self):
        line = "2024-01-01T00:00:00 INFO hello"
        entry = parse_line(line)
        assert entry.format == "iso8601"


class TestNginxFormat:
    def test_access_log(self):
        line = '192.168.1.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326'
        entry = parse_line(line)
        assert entry.format == "nginx_access"
        assert entry.extra.get("status") == "200"
        assert entry.extra.get("host") == "192.168.1.1"


class TestSyslogFormat:
    def test_syslog_line(self):
        line = "Jan 15 12:34:56 myhost myapp: Something happened"
        entry = parse_line(line)
        assert entry.format == "syslog"
        assert entry.extra.get("host") == "myhost"
        assert "Something happened" in entry.message


class TestParseLines:
    def test_accepts_generator(self):
        entries = parse_lines(line for line in ["INFO one", "ERROR two"])
        assert [entry.level for entry in entries] == [LogLevel.INFO, LogLevel.ERROR]

    def test_filters_blank_lines(self):
        lines = ["INFO hello\n", "\n", "  \n", "ERROR world\n"]
        entries = parse_lines(lines)
        assert len(entries) == 2

    def test_returns_list(self):
        result = parse_lines(["INFO test"])
        assert isinstance(result, list)
        assert all(isinstance(e, LogEntry) for e in result)


class TestLogEntry:
    def test_is_error_true(self):
        entry = parse_line("ERROR something failed")
        assert entry.is_error is True

    def test_is_error_critical(self):
        entry = parse_line("CRITICAL total failure")
        assert entry.is_error is True

    def test_is_error_false(self):
        entry = parse_line("INFO all good")
        assert entry.is_error is False

    def test_raw_preserved(self):
        raw = "INFO some log message"
        entry = parse_line(raw)
        assert entry.raw == raw

    def test_empty_line_is_preserved_as_unknown(self):
        entry = parse_line("")
        assert entry.level == LogLevel.UNKNOWN
        assert entry.message == ""


class TestParseFile:
    def test_parse_file(self, tmp_path):
        from logsight.parser import parse_file

        log_content = textwrap.dedent("""\
            2024-01-01T00:00:01 INFO  startup complete
            2024-01-01T00:00:02 ERROR disk full
            2024-01-01T00:00:03 WARNING low memory
        """)
        f = tmp_path / "test.log"
        f.write_text(log_content)

        entries = list(parse_file(str(f)))
        assert len(entries) == 3
        assert entries[1].level == LogLevel.ERROR
        assert entries[2].level == LogLevel.WARNING
