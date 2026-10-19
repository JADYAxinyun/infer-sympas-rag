#!/usr/bin/env python3
"""Normalize common Infer JSON issue fields for the review UI."""
import json


def normalize_report(report):
    issues = report if isinstance(report, list) else report.get("issues", [])
    findings = []
    slices = []
    slice_errors = []
    for issue in issues:
        rule = issue.get("bug_type", issue.get("rule", "unknown"))
        qualifier = issue.get("qualifier", issue.get("description", ""))
        if rule == "SYMPAS_SLICE":
            if "sympas_json=" in qualifier:
                try:
                    evidence, _ = json.JSONDecoder().raw_decode(qualifier.split("sympas_json=", 1)[1])
                    if not isinstance(evidence, dict) or evidence.get("kind") != "SYMPAS_SLICE":
                        raise ValueError("invalid structured slice kind")
                    slices.append(evidence)
                except ValueError as exc:
                    slice_errors.append({"procedure": issue.get("procedure"),
                                         "analysis_status": "failed", "reason": str(exc)})
            else:
                slice_errors.append({"procedure": issue.get("procedure"),
                                     "analysis_status": "unsupported",
                                     "reason": "legacy_checker_without_structured_evidence"})
        findings.append({
            "rule": issue.get("bug_type", issue.get("rule", "unknown")),
            "severity": issue.get("severity", "warning"),
            "file": issue.get("file", issue.get("qualifier")),
            "line": issue.get("line", issue.get("line_number")),
            "message": issue.get("qualifier", issue.get("description", "")),
            "source": "infer",
        })
    return {"findings": findings, "slices": slices, "slice_errors": slice_errors, "summary": {"count": len(findings), "source": "infer"}}
