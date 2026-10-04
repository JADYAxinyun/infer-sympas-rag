#!/usr/bin/env python3
"""Summarize all Infer JSON reports below a test root."""
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("infer-sympas/tests")
    reports = sorted(root.glob("**/sympas-out-ci/report.json"))
    if not reports:
        print(f"no reports found under {root}", file=sys.stderr)
        return 1
    total = 0
    print("suite,issues,functions")
    for report in reports:
        items = json.loads(report.read_text())
        functions = {item.get("procedure", "<unknown>") for item in items}
        suite = report.parts[-3]
        print(f"{suite},{len(items)},{len(functions)}")
        total += len(items)
    print(f"TOTAL,{total},-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
