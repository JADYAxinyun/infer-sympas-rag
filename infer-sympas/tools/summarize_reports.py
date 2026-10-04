#!/usr/bin/env python3
"""Summarize Infer JSON reports emitted by the SymPas checker."""
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} REPORT.json", file=sys.stderr)
        return 2
    reports = json.loads(Path(sys.argv[1]).read_text())
    functions = sorted({item.get("procedure", "<unknown>") for item in reports})
    print(f"issues: {len(reports)}")
    print(f"functions: {len(functions)}")
    for function in functions:
        print(f"- {function}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
