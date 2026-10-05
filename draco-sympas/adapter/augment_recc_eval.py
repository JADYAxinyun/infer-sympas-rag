#!/usr/bin/env python3
"""Augment each DraCo ReccEval prompt with a Python AST slice of its input."""
import json
import sys
from pathlib import Path
from python_slice import slice_source, token_fallback


def inject_facts(prompt: str, facts: str) -> str:
    """Keep the code prefix as the final part of the prompt.

    DraCo asks the model to complete the last line, so appending facts after
    the prefix makes the model continue the facts instead of the program.
    """
    marker = "'''"
    index = prompt.find(marker)
    if index >= 0:
        return prompt[:index] + facts + "\n" + prompt[index:]
    return facts + "\n" + prompt


def main():
    if len(sys.argv) != 4:
        print(f"usage: {Path(sys.argv[0]).name} METADATA.jsonl PROMPTS.jsonl OUTPUT.jsonl", file=sys.stderr)
        return 2
    metadata, prompts, output = map(Path, sys.argv[1:])
    items = [json.loads(line) for line in metadata.open()]
    with prompts.open() as src, output.open("w") as dst:
        for item, prompt_line in zip(items, src):
            prompt = json.loads(prompt_line)
            source = item.get("input", "")
            try:
                lines, frontier = slice_source(source)
                facts = ("\n\n# Static facts from Python slice\n"
                         f"- slice lines: {lines}\n"
                         f"- dependency frontier: {frontier}\n")
            except (SyntaxError, AttributeError, ValueError, TypeError):
                lines, frontier = token_fallback(source)
                facts = ("\n\n# Static facts from token fallback\n"
                         f"- slice lines: {lines}\n"
                         f"- dependency frontier: {frontier}\n")
            dst.write(json.dumps(inject_facts(prompt, facts), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
