#!/usr/bin/env python3
"""Small Python AST backward slicer for DRaCo prompt inputs.

This is an integration baseline, not a replacement for Infer-SymPas.
"""
import ast
import json
import sys
from pathlib import Path


def names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def slice_source(source):
    tree = ast.parse(source)
    statements = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return))]
    statements.sort(key=lambda n: n.lineno)
    needed = set()
    selected = set()
    if statements and isinstance(statements[-1], ast.Return) and statements[-1].value is not None:
        needed |= names(statements[-1].value)
        selected.add(statements[-1].lineno)
    for node in reversed(statements[:-1]):
        targets = names(node.targets[0]) if hasattr(node, "targets") else set()
        if targets & needed:
            selected.add(node.lineno)
            needed |= names(node.value)
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
