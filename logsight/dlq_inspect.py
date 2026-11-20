"""Offline, metadata-only inspection of restricted Kafka DLQ envelopes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dead_letter import inspect_quarantine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a restricted DLQ envelope; never print its raw payload"
    )
    parser.add_argument("path", type=Path, help="Local operator-controlled envelope file")
    args = parser.parse_args()
    try:
        if args.path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("DLQ envelope is too large")
        summary = inspect_quarantine(args.path.read_bytes())
    except (OSError, ValueError) as exc:
        # Avoid printing exception details that might include file paths
        # or untrusted contents.
        print("DLQ inspection failed: invalid or inaccessible envelope", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
