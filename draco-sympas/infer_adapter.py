#!/usr/bin/env python3
"""Normalize common Infer JSON issue fields for the review UI."""


def normalize_report(report):
    issues = report if isinstance(report, list) else report.get("issues", [])
    findings = []
    for issue in issues:
        findings.append({
            "rule": issue.get("bug_type", issue.get("rule", "unknown")),
            "severity": issue.get("severity", "warning"),
            "file": issue.get("file", issue.get("qualifier")),
            "line": issue.get("line", issue.get("line_number")),
            "message": issue.get("qualifier", issue.get("description", "")),
            "source": "infer",
        })
    return {"findings": findings, "summary": {"count": len(findings), "source": "infer"}}
