import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from infer_adapter import normalize_report


def test_preserves_checker_evidence_without_reconstructing_dependencies():
    evidence = {"kind": "SYMPAS_SLICE", "procedure": "callee", "analysis_status": "partial",
                "data_dependencies": ["memory(formal[0])"], "source_locations": []}
    result = normalize_report([{"bug_type": "SYMPAS_SLICE", "qualifier":
                              "evidence; sympas_json=" + json.dumps(evidence) + ". "}])
    assert result["slices"] == [evidence]
    assert not result["slice_errors"]


def test_malformed_slice_is_explicit_failure():
    result = normalize_report([{"bug_type": "SYMPAS_SLICE", "qualifier": "sympas_json={"}])
    assert not result["slices"]
    assert result["slice_errors"][0]["analysis_status"] == "failed"


def test_legacy_slice_does_not_fabricate_structured_evidence():
    result = normalize_report([{"bug_type": "SYMPAS_SLICE", "qualifier": "frontier={ x }"}])
    assert not result["slices"]
    assert result["slice_errors"][0]["analysis_status"] == "unsupported"
