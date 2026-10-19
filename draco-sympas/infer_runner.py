#!/usr/bin/env python3
"""Run Infer, preserving commands and raw output without reusing stale reports."""
import json
import subprocess
from pathlib import Path

from infer_adapter import normalize_report


def run_infer(project, build_command, infer_bin='infer', results_dir=None, *, sympas_only=False, timeout=120, checker_args=None):
    project = Path(project).resolve()
    results = Path(results_dir or project / 'infer-out').resolve()
    results.mkdir(parents=True, exist_ok=True)
    report_path = results / 'report.json'
    if report_path.exists():
        return dict(ok=False, status='results_exist', returncode=None, findings=[],
                    stdout='', stderr='Use a fresh results directory to preserve prior evidence.', commands=[])
    options = ['--sympas-only'] if sympas_only else list(checker_args or [])
    commands = [[infer_bin, 'capture'] + options + ['--results-dir', str(results), '--'] + list(build_command),
                [infer_bin, 'analyze'] + options + ['--results-dir', str(results)]]
    logs = []
    for command in commands:
        try:
            completed = subprocess.run(command, cwd=project, text=True, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            return dict(ok=False, status='execution_failed', returncode=None, stdout='',
                        stderr=type(error).__name__, findings=[], commands=logs + [dict(command=command)])
        logs.append(dict(command=command, returncode=completed.returncode,
                         stdout=completed.stdout, stderr=completed.stderr))
        if completed.returncode:
            return dict(ok=False, status='execution_failed', returncode=completed.returncode,
                        stdout=completed.stdout, stderr=completed.stderr, findings=[], commands=logs)
    if not report_path.exists():
        return dict(ok=False, status='missing_report', returncode=0, stdout='', stderr='report.json missing',
                    findings=[], commands=logs)
    try:
        raw = json.loads(report_path.read_text())
        normalized = normalize_report(raw)
    except (ValueError, TypeError, AttributeError):
        return dict(ok=False, status='report_parse_failed', returncode=0, stdout='', stderr='Invalid Infer JSON', findings=[], commands=logs)
    normalized.update(ok=True, status='ok', returncode=0, report=str(report_path), raw_report=raw, commands=logs)
    return normalized
