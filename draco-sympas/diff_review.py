#!/usr/bin/env python3
"""Extract added Python lines from a unified diff for the first review demo."""
import re
from review import review_source


def review_diff(diff: str):
    file_name = None
    added = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            file_name = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    result = review_source("\n".join(added))
    for finding in result["findings"]:
        finding["file"] = file_name
        finding["scope"] = "added_lines_only"
    result["files"] = [file_name] if file_name else []
    return result
