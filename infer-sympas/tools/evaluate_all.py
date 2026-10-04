#!/usr/bin/env python3
"""Aggregate line-level metrics across truth/report pairs."""
import sys
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import evaluate_locations


def main() -> int:
    if len(sys.argv) < 3 or len(sys.argv[1:]) % 2:
        print(f"usage: {Path(sys.argv[0]).name} TRUTH REPORT [TRUTH REPORT ...]", file=sys.stderr)
        return 2
    tp = predicted = expected = 0
    for i in range(1, len(sys.argv), 2):
        truth = evaluate_locations.load_truth(Path(sys.argv[i]))
        pred = evaluate_locations.load_prediction(Path(sys.argv[i + 1]))
        tp += len(truth & pred)
        predicted += len(pred)
        expected += len(truth)
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print(f"true_positive: {tp}")
    print(f"predicted: {predicted}")
    print(f"expected: {expected}")
    print(f"precision: {precision:.4f}")
    print(f"recall: {recall:.4f}")
    print(f"f1: {f1:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
