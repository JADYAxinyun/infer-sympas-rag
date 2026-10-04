#!/usr/bin/env python3
"""Compute line-level Precision/Recall/F1 from a labeled JSON file and report.json."""
import json
import re
import sys
from pathlib import Path


def load_truth(path: Path) -> set[tuple[str, int]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = [data]
    return {(item["function"], int(loc["line"])) for item in data for loc in item["expected_locations"]}


def load_prediction(path: Path) -> set[tuple[str, int]]:
    result = set()
    for item in json.loads(path.read_text()):
        function = item.get("procedure", "<unknown>")
        qualifier = item.get("qualifier", "")
        for line in re.findall(r"line (\d+)", qualifier):
            result.add((function, int(line)))
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {Path(sys.argv[0]).name} GROUND_TRUTH.json REPORT.json", file=sys.stderr)
        return 2
    truth = load_truth(Path(sys.argv[1]))
    prediction = load_prediction(Path(sys.argv[2]))
    tp = len(truth & prediction)
    precision = tp / len(prediction) if prediction else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print(f"true_positive: {tp}")
    print(f"predicted: {len(prediction)}")
    print(f"expected: {len(truth)}")
    print(f"precision: {precision:.4f}")
    print(f"recall: {recall:.4f}")
    print(f"f1: {f1:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
