#!/usr/bin/env python3
"""Normalize Infer JSON issues and preserve low-confidence SymPas contract candidates."""
import re
import json


CONTRACT = re.compile(r"callee=(?P<callee>[^;]+); kind=(?P<kind>[^;]+); confidence=(?P<confidence>[^;]+); evidence=(?P<evidence>.*)$")


def normalize_report(report):
    issues = report if isinstance(report, list) else report.get("issues", [])
    findings = []
    return_contract_candidates = []
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
        if rule == "SYMPAS_RETURN_CONTRACT_CANDIDATE":
            match = CONTRACT.search(qualifier)
            if match:
                candidate = match.groupdict()
                candidate["evidence"] = candidate["evidence"].rstrip(".")
                candidate.update({"source": "infer", "procedure": issue.get("procedure"), "file": issue.get("file"), "line": issue.get("line")})
                return_contract_candidates.append(candidate)
        findings.append({
            "rule": rule,
            "severity": issue.get("severity", "warning"),
            "file": issue.get("file", issue.get("qualifier")),
            "line": issue.get("line", issue.get("line_number")),
            "message": qualifier,
            "source": "infer",
        })
    return {"findings": findings, "return_contract_candidates": return_contract_candidates,
            "slices": slices, "slice_errors": slice_errors,
            "summary": {"count": len(findings), "source": "infer"}}
