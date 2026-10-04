#!/usr/bin/env python3
"""Small Python AST backward slicer for DRaCo prompt inputs.

This is an integration baseline, not a replacement for Infer-SymPas.
"""
import ast
import io
import json
import keyword
import tokenize
import sys
from pathlib import Path


def names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def parse_prefix(source):
    candidates = [source, source + "\npass"]
    stripped = source.rstrip()
    if stripped.endswith(":"):
        indent = len(stripped.split("\n")[-1]) - len(stripped.split("\n")[-1].lstrip()) + 4
        candidates.append(stripped + "\n" + " " * indent + "pass")
    if stripped.endswith("."):
        candidates.append(stripped + "__completion__")
    last_error = None
    for candidate in candidates:
        try:
            return ast.parse(candidate)
        except SyntaxError as error:
            last_error = error
    raise last_error


def token_fallback(source):
    visible = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.NAME and not keyword.iskeyword(token.string):
                visible.add(token.string)
    except (tokenize.TokenError, IndentationError):
        pass
    lines = source.splitlines()
    last = next((i for i in range(len(lines), 0, -1) if lines[i - 1].strip()), 0)
    return ([last] if last else []), sorted(visible)


def slice_source(source):
    try:
        tree = parse_prefix(source)
    except (SyntaxError, IndentationError):
        return token_fallback(source)
    statements = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return))]
    statements.sort(key=lambda n: n.lineno)
    needed = set()
    selected = set()
    criterion = statements[-1] if statements else None
    if isinstance(criterion, ast.Return) and criterion.value is not None:
        needed |= names(criterion.value)
        selected.add(criterion.lineno)
    elif isinstance(criterion, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        needed |= names(criterion.value)
        selected.add(criterion.lineno)
    for node in reversed(statements[:-1] if criterion is not None else statements):
        targets = names(node.targets[0]) if hasattr(node, "targets") else set()
        if targets & needed:
            selected.add(node.lineno)
            needed |= names(node.value)
    if not selected:
        # Conservative completion fallback: retain the last source line and
        # visible names rather than silently producing an empty context.
        source_lines = [line for line in source.splitlines() if line.strip()]
        if source_lines:
            selected.add(len(source.splitlines()))
            needed |= names(tree)
    return sorted(selected), sorted(needed)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} SOURCE.py", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).read_text()
    lines, frontier = slice_source(source)
    print(json.dumps({"slice_lines": lines, "frontier": frontier}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
