#!/usr/bin/env python3
"""Run the local DRaCo + Python-slice prompt pipeline."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "draco-sympas/artifacts/draco-prompts.jsonl"
METADATA = ROOT / "third_party/draco-upstream/ReccEval/metadata.jsonl"
OUTPUT = ROOT / "draco-sympas/artifacts/draco-prompts-sympas.jsonl"
ADAPTER = ROOT / "draco-sympas/adapter/augment_recc_eval.py"


def main():
    if not PROMPTS.exists():
        print("missing original DraCo prompts; run upstream src/main.py first", file=sys.stderr)
        return 1
    subprocess.run([sys.executable, str(ADAPTER), str(METADATA), str(PROMPTS), str(OUTPUT)], check=True)
    print(f"generated: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
