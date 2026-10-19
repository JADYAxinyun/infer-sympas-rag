#!/usr/bin/env python3
"""Small explainable rule for the first end-to-end review demo."""
import re

from contracts import infer_candidate_contracts, merge_return_contracts

# Also accept common C/Java declarations such as ``int ret = open_config``.
# This is a deliberately conservative prototype policy, not inferred API
# semantics: unknown callees are not reported until a return-value contract is
# available from a language frontend or static analysis.
CALL = re.compile(
    r"^\s*(?:(?:const\s+)?[A-Za-z_]\w*(?:\s*\*\s*)?\s+)?"
    r"(?P<var>[A-Za-z_]\w*)\s*=\s*(?P<callee>[A-Za-z_]\w*)\s*\("
)


def review_source(source: str, return_contracts=None, infer_candidates=None):
    lines = source.splitlines()
    contracts = merge_return_contracts(infer_candidate_contracts(infer_candidates))
    contracts.update(merge_return_contracts(return_contracts))
    findings = []
    for index, line in enumerate(lines):
        match = CALL.match(line)
        if not match:
            continue
        variable, callee = match.group("var"), match.group("callee")
        contract = contracts.get(callee)
        is_confirmed = contract and contract.get("kind") == "status"
        is_infer_candidate = contract and contract.get("kind") == "status_candidate" and contract.get("confidence") == "medium"
        if not contract or not contract.get("checks_required") or not (is_confirmed or is_infer_candidate):
            continue
        checked = any(re.search(rf"\bif\s+.*\b{re.escape(variable)}\b", item) for item in lines[index + 1:index + 6])
        if not checked:
            findings.append({"rule": "unchecked_return_value", "severity": "medium" if is_confirmed else "low", "line": index + 1,
                             "callee": callee, "variable": variable,
                             "message": (f"返回值 {variable} 来自 {callee}，但附近没有发现条件检查。" if is_confirmed
                                         else f"Infer 候选显示 {callee} 可能返回负错误码；返回值 {variable} 附近未见条件检查，需人工确认 API 契约。"),
                             "suggestion": (f"检查 {variable} 后再继续执行，或显式记录为何可以忽略。" if is_confirmed
                                            else f"确认 {callee} 的返回值契约；若负值表示错误，请检查 {variable} 后再继续执行。"),
                             "contract": {"callee": callee, "kind": contract["kind"], "source": contract.get("source", "unknown"), "evidence": contract.get("evidence", "")}})
    return {"findings": findings, "summary": {"count": len(findings), "policy": "return_contract"}}
