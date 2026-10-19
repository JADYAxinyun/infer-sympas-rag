import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from infer_adapter import normalize_report


def test_normalizes_infer_issue():
    result = normalize_report([{"bug_type": "DEAD_STORE", "file": "a.c", "line": 2, "qualifier": "unused"}])
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["source"] == "infer"


def test_preserves_low_confidence_sympas_contract_candidate():
    report = [{"bug_type": "SYMPAS_RETURN_CONTRACT_CANDIDATE", "procedure": "open_config", "file": "a.c", "line": 2,
               "qualifier": "SymPas return contract candidate: callee=open_config; kind=status_candidate; confidence=low; evidence=integral_return_type"}]
    result = normalize_report(report)
    assert result["return_contract_candidates"] == [{"callee": "open_config", "kind": "status_candidate", "confidence": "low", "evidence": "integral_return_type", "source": "infer", "procedure": "open_config", "file": "a.c", "line": 2}]
