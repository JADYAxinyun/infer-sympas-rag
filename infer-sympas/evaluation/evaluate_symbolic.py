#!/usr/bin/env python3
"""Run real Infer and assert machine-readable symbolic output summaries.

INFER_BIN must identify an Infer build containing this project's checker.
This is a rule-based regression, not an independently annotated benchmark.
"""
import argparse
import json
import os
import platform
from pathlib import Path
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def evaluate(infer, source, expected, timeout=60):
    with tempfile.TemporaryDirectory(prefix="sympas-symbolic-") as tmp:
        started = time.perf_counter()
        command = [infer, "--sympas-only", "--results-dir", str(Path(tmp) / "out"),
                   "--", "clang", "-c", str(source), "-o", str(Path(tmp) / "case.o")]
        run = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - started
        if run.returncode:
            raise RuntimeError(run.stdout + run.stderr)
        report_path = Path(tmp) / "out" / "report.json"
        report = json.loads(report_path.read_text())
        slices = {}
        for issue in report:
            if issue.get("bug_type") != "SYMPAS_SLICE":
                continue
            text = issue["qualifier"]
            marker = "sympas_json="
            if marker not in text:
                raise AssertionError("Checker lacks structured evidence; rebuild Infer")
            evidence, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
            slices[issue["procedure"]] = evidence
        checks = []
        for procedure, reference in expected.items():
            actual = slices.get(procedure)
            summary = actual["procedure_summary"] if actual else {}
            returned = sorted(summary.get("return_dependencies", []))
            wanted = sorted(reference.get("return_dependencies", []))
            missing = sorted(set(wanted) - set(returned))
            extra = sorted(set(returned) - set(wanted))
            matches = not missing and (not extra or reference.get("allow_conservative_extra", False))
            checks.append({"procedure": procedure, "field": "return_dependencies",
                           "expected": wanted, "actual": returned,
                           "missing": missing, "extra": extra,
                           "comparison": "required_subset" if reference.get("allow_conservative_extra") else "exact",
                           "ok": actual is not None and matches})
            controls = {item["location"]["line"] for item in (actual or {}).get("control_dependencies", [])}
            if "control_lines" in reference:
                wanted_controls = sorted(reference["control_lines"])
                checks.append({"procedure": procedure, "field": "control_lines",
                               "expected": wanted_controls, "actual": sorted(controls),
                               "ok": actual is not None and wanted_controls == sorted(controls)})
            for field, must_exist in (("required_control_lines", True), ("excluded_control_lines", False)):
                for line in reference.get(field, []):
                    checks.append({"procedure": procedure, "field": field, "line": line,
                                   "actual_control_lines": sorted(controls),
                                   "ok": (line in controls) == must_exist})
            for target, deps in reference.get("outputs", {}).items():
                output = next((item for item in summary.get("outputs", [])
                               if item["target"] == target), None)
                found = sorted(output["dependencies"]) if output else None
                checks.append({"procedure": procedure, "field": target,
                               "expected": sorted(deps), "actual": found,
                               "ok": found == sorted(deps)})
        return {"source": str(source.relative_to(ROOT)), "criterion": "return_value_and_output_memory",
                "command": [infer, "--sympas-only", "--results-dir", "<temporary>/out",
                            "--", "clang", "-c", str(source.relative_to(ROOT.parent)),
                            "-o", "<temporary>/case.o"],
                "working_directory": "repository_root", "expectations": expected,
                "runtime_seconds": elapsed, "output_bytes": report_path.stat().st_size,
                "slice_sizes": {name: len(value.get("source_locations", []))
                                for name, value in slices.items()},
                "termination": "completed_within_timeout",
                "timeout_seconds": timeout,
                "missing_dependencies": sum(len(check.get("missing", [])) for check in checks),
                "extra_dependencies": sum(len(check.get("extra", [])) for check in checks),
                "checks": checks, "actual_slices": slices,
                "ok": all(check["ok"] for check in checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--infer", default=os.environ.get("INFER_BIN"))
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("symbolic_cases.json"))
    parser.add_argument("--output", type=Path, help="optional generated JSON report")
    args = parser.parse_args()
    if not args.infer:
        parser.error("provide --infer or INFER_BIN")
    cases = json.loads(args.manifest.read_text())
    if not isinstance(cases, list) or not cases:
        parser.error("manifest must contain at least one regression case")
    if any(not case.get("expected") for case in cases):
        parser.error("each regression case requires explicit expectations")
    results = []
    for case in cases:
        try:
            results.append(evaluate(args.infer, ROOT / case["source"], case["expected"]))
        except (subprocess.TimeoutExpired, RuntimeError, AssertionError, KeyError, ValueError, OSError) as exc:
            results.append({"source": case["source"], "ok": False,
                            "analysis_status": "failed", "error": str(exc)})
    try:
        version = subprocess.run([args.infer, "--version"], capture_output=True, text=True, check=True)
        infer_version = (version.stdout or version.stderr).splitlines()[0]
        version_status = "ok"
    except (OSError, subprocess.CalledProcessError, IndexError):
        infer_version, version_status = "unknown", "failed"
    checks = [check for case in results for check in case.get("checks", [])]
    sccs = {}
    for case in results:
        for value in case.get("actual_slices", {}).values():
            fixed = value.get("procedure_summary", {}).get("fixed_point", {})
            if fixed.get("members"):
                key = (case["source"], tuple(fixed["members"]))
                sccs[key] = {"source": case["source"], **fixed}
    result = {"evaluation": "rule_based_regression",
                      "environment": {"infer": infer_version, "version_status": version_status,
                                      "system": platform.system(), "machine": platform.machine(),
                                      "python": platform.python_version()},
                      "limitation": "当前只有规则化回归测试，尚未完成基于人工参考切片的完整精度评估。",
                      "statistics": {"assertions": len(checks),
                                     "passed_assertions": sum(check["ok"] for check in checks),
                                     "failed_cases": sum(not case["ok"] for case in results),
                                     "missing_dependencies": sum(case.get("missing_dependencies", 0) for case in results),
                                     "extra_dependencies": sum(case.get("extra_dependencies", 0) for case in results),
                                     "total_runtime_seconds": sum(case.get("runtime_seconds", 0) for case in results),
                                     "total_output_bytes": sum(case.get("output_bytes", 0) for case in results),
                                     "scc_results": list(sccs.values())},
                      "cases": results}
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if version_status == "ok" and all(case["ok"] for case in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
