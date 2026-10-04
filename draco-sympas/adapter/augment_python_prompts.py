#!/usr/bin/env python3
"""Append Python AST slice facts to a DraCo prompt JSONL file."""
import json
import sys
from pathlib import Path
from python_slice import slice_source


def main():
    if len(sys.argv) != 4:
        print(f"usage: {Path(sys.argv[0]).name} PROMPTS.jsonl SOURCE.py OUTPUT.jsonl", file=sys.stderr)
        return 2
    prompts, source, output = map(Path, sys.argv[1:])
    source_text = source.read_text()
    lines, frontier = slice_source(source_text)
    facts = ("\n\n# Static facts from Python slice\n"
             f"- slice lines: {lines}\n"
             f"- dependency frontier: {frontier}\n")
    with prompts.open() as src, output.open("w") as dst:
        for line in src:
            dst.write(json.dumps(json.loads(line) + facts, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
