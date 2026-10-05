import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from infer_adapter import normalize_report


def test_normalizes_infer_issue():
    result = normalize_report([{"bug_type": "DEAD_STORE", "file": "a.c", "line": 2, "qualifier": "unused"}])
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["source"] == "infer"
