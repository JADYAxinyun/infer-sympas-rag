#!/usr/bin/env python3
"""Run one complete local code-review demo and save a JSON report."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapter"))

from infer_adapter import normalize_report  # noqa: E402
from llm_service import explain  # noqa: E402
from python_slice import slice_source, token_fallback  # noqa: E402
from review import review_source  # noqa: E402


def main():
    source_path = Path(__file__).with_name("unchecked_return.c")
    source = source_path.read_text()
    try:
        lines, frontier = slice_source(source)
        method = "ast"
    except (SyntaxError, AttributeError, ValueError, TypeError):
        lines, frontier = token_fallback(source)
        method = "token_fallback"

    result = {
        "source": {"file": str(source_path), "language": "c"},
        "slice": {"method": method, "slice_lines": lines, "frontier": frontier},
        "review": review_source(source),
        "verification": {
            "status": "candidate",
            "note": "This demo runs the local rule and LLM; Infer validation is supplied separately when available.",
        },
    }
    infer_bin = os.environ.get("INFER_BIN", "infer")
    infer_dir = ROOT / "artifacts" / "infer-e2e-out"
    capture = subprocess.run(
        [infer_bin, "capture", "--sympas-only", "--results-dir", str(infer_dir), "--",
         "clang", "-c", str(source_path)], cwd=ROOT, text=True, capture_output=True
    )
    infer_report = infer_dir / "report.json"
    if capture.returncode == 0:
        analyze = subprocess.run(
            [infer_bin, "analyze", "--sympas-only", "--results-dir", str(infer_dir)],
            cwd=ROOT, text=True, capture_output=True
        )
        if analyze.returncode == 0 and infer_report.exists():
            result["infer"] = normalize_report(json.loads(infer_report.read_text()))
    result.setdefault("infer", {"findings": [], "summary": {"count": 0, "source": "infer"}})
    result["llm"] = {"model": "Salesforce/codegen-350M-mono", "explanation": explain(result)}
    output = ROOT / "artifacts" / "e2e-unchecked-return.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"output": str(output), "finding_count": result["review"]["summary"]["count"],
                      "llm": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
