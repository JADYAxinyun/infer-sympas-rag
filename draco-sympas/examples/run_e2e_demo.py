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
from repair import propose_return_check  # noqa: E402
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

    def infer_for(path, label):
        infer_dir = ROOT / "artifacts" / f"infer-{label}"
        capture = subprocess.run(
            [infer_bin, "capture", "--sympas-only", "--results-dir", str(infer_dir), "--",
             "clang", "-c", str(path)], cwd=ROOT, text=True, capture_output=True
        )
        infer_report = infer_dir / "report.json"
        if capture.returncode != 0:
            return {"findings": [], "summary": {"count": 0, "source": "infer"},
                    "status": "capture_failed"}
        analyze = subprocess.run(
            [infer_bin, "analyze", "--sympas-only", "--results-dir", str(infer_dir)],
            cwd=ROOT, text=True, capture_output=True
        )
        if analyze.returncode != 0 or not infer_report.exists():
            return {"findings": [], "summary": {"count": 0, "source": "infer"},
                    "status": "analyze_failed"}
        normalized = normalize_report(json.loads(infer_report.read_text()))
        normalized["status"] = "ok"
        return normalized

    result["infer"] = infer_for(source_path, "e2e-out")
    result.setdefault("infer", {"findings": [], "summary": {"count": 0, "source": "infer"}})
    result["llm"] = {"model": "Salesforce/codegen-350M-mono", "explanation": explain(result)}
    review_findings = result["review"].get("findings", [])
    infer_findings = result["infer"].get("findings", [])
    primary = review_findings[0] if review_findings else (infer_findings[0] if infer_findings else {})
    result["structured_report"] = {
        "problem": primary.get("rule", "no_configured_finding"),
        "evidence": infer_findings + review_findings,
        "slice": result["slice"],
        "llm_explanation": result["llm"]["explanation"],
        "suggestion": primary.get("suggestion", "等待人工确认后再应用修改。"),
        "verification": result["verification"],
    }
    repair = propose_return_check(source, review_findings[0]) if review_findings else None
    if repair:
        after = review_source(repair["source"])
        fixed_path = ROOT / "artifacts" / "unchecked_return_fixed.c"
        fixed_path.parent.mkdir(exist_ok=True)
        fixed_path.write_text(repair["source"])
        infer_after = infer_for(fixed_path, "e2e-fixed")
        result["repair"] = {
            "status": "verified" if after["summary"]["count"] < len(review_findings) else "not_verified",
            "strategy": repair["strategy"],
            "changed_line": repair["line"],
            "before_findings": len(review_findings),
            "after_findings": after["summary"]["count"],
            "infer_after": infer_after,
            "patched_source": repair["source"],
        }
    else:
        result["repair"] = {"status": "not_available"}
    output = ROOT / "artifacts" / "e2e-unchecked-return.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"output": str(output), "finding_count": result["review"]["summary"]["count"],
                      "infer_finding_count": result["infer"]["summary"]["count"], "llm": True},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
