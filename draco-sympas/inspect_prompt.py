#!/usr/bin/env python3
"""Inspect one generated DraCo prompt by zero-based record index."""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {Path(sys.argv[0]).name} PROMPTS.jsonl [INDEX]", file=sys.stderr)
        return 2
    index = int(sys.argv[2]) if len(sys.argv) == 3 else 0
    with Path(sys.argv[1]).open() as f:
        for i, line in enumerate(f):
            if i == index:
                print(json.loads(line))
                return 0
    print(f"index {index} not found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
