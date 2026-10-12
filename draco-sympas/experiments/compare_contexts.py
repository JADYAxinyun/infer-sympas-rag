#!/usr/bin/env python3
"""Compare baseline and SymPas-augmented DRaCo completions on the same samples."""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def metrics(metadata, completions):
    exact = contains = 0
    similarity = 0.0
    for item in completions:
        gold = metadata[item["index"]].get("gt", "").strip().splitlines()[0] if metadata[item["index"]].get("gt", "").strip() else ""
        pred = item.get("completion", "").strip().splitlines()[0] if item.get("completion", "").strip() else ""
        exact += pred == gold
        contains += bool(gold) and gold in item.get("completion", "")
        similarity += SequenceMatcher(None, pred, gold).ratio()
    n = len(completions)
    return {"samples": n, "exact_first_line": exact / n if n else 0.0,
            "contains_gold_first_line": contains / n if n else 0.0,
            "first_line_similarity": similarity / n if n else 0.0}


def main():
    if len(sys.argv) != 4:
        print(f"usage: {Path(sys.argv[0]).name} METADATA BASELINE AUGMENTED", file=sys.stderr)
        return 2
    metadata = load(sys.argv[1])
    baseline = load(sys.argv[2])
    augmented = load(sys.argv[3])
    result = {"baseline": metrics(metadata, baseline), "sympas_augmented": metrics(metadata, augmented)}
    result["delta"] = {key: result["sympas_augmented"][key] - result["baseline"][key]
                        for key in result["baseline"] if key != "samples"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
