#!/usr/bin/env python3
"""Conservative repair for the first supported review rule."""
import re


ASSIGN = re.compile(
    r"^(?P<indent>\s*)(?:(?:const\s+)?[A-Za-z_]\w*(?:\s*\*\s*)?\s+)?"
    r"(?P<var>[A-Za-z_]\w*)\s*=\s*(?P<callee>[A-Za-z_]\w*)\s*\(.*\)\s*;\s*$"
)


def propose_return_check(source: str, finding: dict):
    """Return a candidate patched source, or ``None`` if the rule is unsupported."""
    if finding.get("rule") != "unchecked_return_value":
        return None
    target_line = int(finding.get("line", 0))
    variable = finding.get("variable")
    lines = source.splitlines()
    if not variable or target_line < 1 or target_line > len(lines):
        return None
    match = ASSIGN.match(lines[target_line - 1])
    if not match or match.group("var") != variable:
        return None
    indent = match.group("indent")
    inserted = [
        lines[target_line - 1],
        f"{indent}if ({variable} < 0) {{",
        f"{indent}    return {variable};",
        f"{indent}}}",
    ]
    patched = lines[: target_line - 1] + inserted + lines[target_line:]
    return {"source": "\n".join(patched) + ("\n" if source.endswith("\n") else ""),
            "line": target_line, "variable": variable, "strategy": "negative_return_check"}
