#!/usr/bin/env python3
"""Measure capture/analyze wall time for one C source with Infer."""
import subprocess
import sys
import time
from pathlib import Path


def run(cmd):
    start = time.perf_counter()
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return time.perf_counter() - start


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {Path(sys.argv[0]).name} INFER_BIN SOURCE.c", file=sys.stderr)
        return 2
    infer, source = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    out = source.parent / ".sympas-benchmark-out"
    out.mkdir(exist_ok=True)
    capture = run([str(infer), "--sympas", "--results-dir", str(out), "capture", "--", "clang", "-c", str(source)])
    analyze = run([str(infer), "--sympas", "--results-dir", str(out), "analyze"])
    print(f"capture_seconds: {capture:.3f}")
    print(f"analyze_seconds: {analyze:.3f}")
    print(f"results_bytes: {sum(p.stat().st_size for p in out.rglob('*') if p.is_file())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
