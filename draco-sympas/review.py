#!/usr/bin/env python3
"""Small explainable rule for the first end-to-end review demo."""
import re

# Also accept common C/Java declarations such as ``int ret = open_config``.
# This remains a deliberately small rule; richer syntax belongs in the AST
# and slicing adapters.
CALL = re.compile(
    r"^\s*(?:(?:const\s+)?[A-Za-z_]\w*(?:\s*\*\s*)?\s+)?"
    r"(?P<var>[A-Za-z_]\w*)\s*=\s*(?P<callee>[A-Za-z_]\w*)\s*\("
)


def review_source(source: str):
    lines = source.splitlines()
    findings = []
    for index, line in enumerate(lines):
        match = CALL.match(line)
        if not match:
            continue
        variable, callee = match.group("var"), match.group("callee")
        checked = any(re.search(rf"\bif\s+.*\b{re.escape(variable)}\b", item) for item in lines[index + 1:index + 6])
        if not checked:
            findings.append({"rule": "unchecked_return_value", "severity": "medium", "line": index + 1,
                             "callee": callee, "variable": variable,
                             "message": f"返回值 {variable} 来自 {callee}，但附近没有发现条件检查。",
                             "suggestion": f"检查 {variable} 后再继续执行，或显式记录为何可以忽略。"})
    return {"findings": findings, "summary": {"count": len(findings)}}
