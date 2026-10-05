#!/usr/bin/env python3
"""Render structured analysis into a review report suitable for an LLM or UI."""


def render_markdown(result):
    sections = ["# Code Review Report", ""]
    review = result.get("review", {})
    infer = result.get("infer", {})
    findings = review.get("findings", []) + infer.get("findings", [])
    sections.append(f"发现问题：**{len(findings)}** 个")
    sections.append("")
    if not findings:
        sections.append("未发现已配置规则覆盖的问题。")
    for index, finding in enumerate(findings, 1):
        location = ":".join(str(x) for x in (finding.get("file"), finding.get("line")) if x is not None)
        sections.extend([
            f"## {index}. {finding.get('rule', 'unknown')}",
            f"- 位置：`{location or '未提供'}`",
            f"- 来源：`{finding.get('source', 'local-review')}`",
            f"- 严重程度：`{finding.get('severity', 'unknown')}`",
            f"- 说明：{finding.get('message', '')}",
        ])
        if finding.get("suggestion"):
            sections.append(f"- 建议：{finding['suggestion']}")
        sections.append("")
    return "\n".join(sections)
