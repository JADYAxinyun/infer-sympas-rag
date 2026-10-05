#!/usr/bin/env python3
"""Run Infer on a project command and normalize the generated report."""
import json
import subprocess
from pathlib import Path

from infer_adapter import normalize_report


def run_infer(project, build_command, infer_bin="infer", results_dir=None):
    project = Path(project).resolve()
    results = Path(results_dir or project / "infer-out").resolve()
    results.mkdir(parents=True, exist_ok=True)
    command = [infer_bin, "capture", "--results-dir", str(results), "--"] + list(build_command)
    try:
        completed = subprocess.run(command, cwd=project, text=True, capture_output=True)
    except FileNotFoundError as error:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(error), "findings": []}
    report_path = results / "report.json"
    if not report_path.exists():
        return {"ok": False, "returncode": completed.returncode, "stdout": completed.stdout,
                "stderr": completed.stderr, "findings": []}
    report = json.loads(report_path.read_text())
    normalized = normalize_report(report)
    normalized.update({"ok": completed.returncode == 0, "returncode": completed.returncode,
                       "report": str(report_path)})
    return normalized
