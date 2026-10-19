#!/usr/bin/env python3
"""Compare real SIL-derived slices with pre-authored source-statement references.

These are AI-authored source-derived references, not paper data or independent
human ground truth. Metrics apply only to the annotated source projection.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from evaluate_symbolic import evaluate, ROOT


def statement_map(source):
    labels = {}
    for line, text in enumerate(source.read_text().splitlines(), 1):
        for label in re.findall(r"/\*S:([A-Z0-9_]+)\*/", text):
            if label in labels:
                raise ValueError("duplicate statement label: " + label)
            labels[label] = line
    return labels


def compare(reference, actual, mode):
    if mode not in ("exact", "conservative"):
        raise ValueError("unknown comparison mode")
    reference, actual = set(reference), set(actual)
    common = reference & actual
    precision = len(common) / len(actual) if actual else float(not reference)
    recall = len(common) / len(reference) if reference else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"reference": sorted(reference), "actual": sorted(actual),
            "missing": sorted(reference - actual), "extra": sorted(actual - reference),
            "precision": precision, "recall": recall, "f1": f1,
            "slice_size": len(actual),
            "ok": reference <= actual and (mode == "conservative" or reference == actual)}


def run_reference(infer, manifest):
    if not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        raise ValueError("manifest requires nonempty reference cases")
    source = ROOT / manifest["source"]
    labels = statement_map(source)
    for case in manifest["cases"]:
        if case.get("criterion") != {"type": "return_value"}:
            raise ValueError("reference evaluator supports only whole-procedure return_value criteria")
        if case["mode"] not in ("exact", "conservative"):
            raise ValueError("unknown comparison mode")
        if not case["reference"] or not set(case["reference"]) <= labels.keys():
            raise ValueError("reference contains missing or empty statement labels")
    raw = evaluate(infer, source, {})
    rows = []
    for case in manifest["cases"]:
        evidence = raw["actual_slices"].get(case["procedure"])
        if evidence is None or evidence.get("analysis_status") in ("failed", "unsupported"):
            rows.append({"procedure": case["procedure"], "ok": False,
                         "analysis_status": "failed", "reason": "missing_or_failed_slice"})
            continue
        lines = {loc["line"] for loc in evidence["source_locations"]
                 if Path(loc["file"]).resolve() == source.resolve()}
        actual = {label for label, line in labels.items() if line in lines}
        row = {"procedure": case["procedure"], "criterion": evidence["criterion"],
               "analysis_status": evidence["analysis_status"],
               "mode": case["mode"], **compare(case["reference"], actual, case["mode"]),
               "actual_data_dependencies": evidence["data_dependencies"],
               "actual_control_dependencies": evidence["control_dependencies"]}
        rows.append(row)
    return {"reference_provenance": manifest["provenance"],
            "review_status": manifest["review_status"],
            "comparison_unit": manifest["comparison_unit"],
            "limitations": manifest["scope"], "source": manifest["source"],
            "command": raw["command"], "working_directory": raw["working_directory"],
            "runtime_seconds": raw["runtime_seconds"], "output_bytes": raw["output_bytes"],
            "cases": rows, "passed": sum(case["ok"] for case in rows),
            "total": len(rows), "ok": all(case["ok"] for case in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--infer", default=os.environ.get("INFER_BIN"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("reference_slices.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.infer:
        parser.error("provide INFER_BIN or --infer")
    try:
        result = run_reference(args.infer, json.loads(args.manifest.read_text()))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AssertionError,
            subprocess.TimeoutExpired) as exc:
        result = {"ok": False, "analysis_status": "failed", "reason": str(exc),
                  "cases": [], "passed": 0, "total": 0,
                  "metrics_status": "not_computed"}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
