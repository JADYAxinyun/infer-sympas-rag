#!/usr/bin/env python3
"""Select slice criteria from instruction snapshots emitted by the SIL checker."""
import argparse
import copy
import json
from pathlib import Path


TYPES = ("return_value", "variable", "call_site", "finding_variable", "return_point", "file_location")


def read_slices(report):
    issues = report if isinstance(report, list) else report.get("issues", [])
    slices = []
    for issue in issues:
        if issue.get("bug_type") != "SYMPAS_SLICE":
            continue
        qualifier = issue.get("qualifier", "")
        if "sympas_json=" not in qualifier:
            continue
        value, _ = json.JSONDecoder().raw_decode(qualifier.split("sympas_json=", 1)[1])
        slices.append(value)
    return slices


def select(slices, criterion):
    kind = criterion["type"]
    if kind not in TYPES:
        raise ValueError("unsupported criterion type: " + kind)
    if kind in ("variable", "finding_variable") and not criterion.get("variable"):
        raise ValueError("variable criterion requires variable")
    if kind in ("call_site", "return_point", "file_location", "finding_variable") and not criterion.get("line"):
        raise ValueError("location criterion requires line")
    selected = []
    for procedure in slices:
        if criterion.get("procedure") not in (None, procedure["procedure"]):
            continue
        if kind == "return_value":
            selected.append(copy.deepcopy(procedure))
            continue
        for snapshot in procedure.get("instruction_slices", []):
            loc = snapshot["instruction"]
            if criterion.get("file") and Path(loc["file"]).as_posix() != Path(criterion["file"]).as_posix():
                continue
            if criterion.get("line") and loc["line"] != criterion["line"]:
                continue
            if criterion.get("column") and loc["column"] != criterion["column"]:
                continue
            if kind in ("variable", "finding_variable") and loc.get("target") != criterion["variable"]:
                continue
            if kind == "call_site" and loc.get("event") != "call":
                continue
            if kind == "return_point" and loc.get("target") != "return":
                continue
            result = copy.deepcopy(procedure)
            result.pop("instruction_slices", None)
            result["criterion"] = {"type": kind, "target": criterion.get("variable", loc.get("target")),
                                   "location": loc}
            result["data_dependencies"] = snapshot["data_dependencies"]
            result["source_locations"] = snapshot["source_locations"]
            result["control_dependencies"] = [
                {"location": source, "target": result["criterion"]["target"],
                 "reason": "symbolic_predicate_dependency_conservative"}
                for source in snapshot["source_locations"] if source.get("event") == "control"]
            result["call_chain"] = [
                {"caller": source["procedure"], "callee": source["callee"], "location": source}
                for source in snapshot["source_locations"] if source.get("event") == "call"]
            selected.append(result)
    if not selected:
        return [{"kind": "SYMPAS_SLICE", "criterion": criterion,
                 "analysis_status": "unsupported", "precision": "unknown",
                 "reason": "no_matching_sil_definition_or_location"}]
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--type", choices=TYPES, default="return_value")
    parser.add_argument("--procedure")
    parser.add_argument("--variable")
    parser.add_argument("--file")
    parser.add_argument("--line", type=int)
    parser.add_argument("--column", type=int)
    args = vars(parser.parse_args())
    report = json.loads(args.pop("report").read_text())
    result = select(read_slices(report), {key: value for key, value in args.items() if value is not None})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if any(item["analysis_status"] == "unsupported" for item in result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
