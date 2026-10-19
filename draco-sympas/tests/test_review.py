import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from review import review_source


def test_reports_unchecked_return():
    result = review_source("def f(x):\n    ret = load_config(x)\n    return ret")
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["rule"] == "unchecked_return_value"


def test_accepts_checked_return():
    result = review_source("def f(x):\n    ret = load_config(x)\n    if ret < 0:\n        return ret\n    return 0")
    assert result["summary"]["count"] == 0


def test_reports_c_style_declaration():
    result = review_source("int f(const char *path) {\n    int ret = open_config(path);\n    continue_running();\n}")
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["callee"] == "open_config"


def test_ignores_numerical_return_when_no_status_contract_is_configured():
    result = review_source("def f(x):\n    transformed = logit(x)\n    return transformed")
    assert result["summary"]["count"] == 0
    assert result["summary"]["policy"] == "return_contract"


def test_request_contract_can_enable_an_unknown_status_callee():
    source = "def f(path):\n    rc = third_party_call(path)\n    continue_running()"
    result = review_source(source, {"third_party_call": {"kind": "status", "checks_required": True, "source": "infer", "evidence": "summary"}})
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["contract"]["source"] == "infer"


def test_non_status_request_contract_does_not_report():
    result = review_source("x = transform(value)", {"transform": {"kind": "value", "source": "infer"}})
    assert result["summary"]["count"] == 0


def test_medium_infer_candidate_reports_unchecked_call_as_needs_confirmation():
    source = "int f(const char *path) {\n    int rc = inferred_api(path);\n    continue_running();\n}"
    candidate = {"callee": "inferred_api", "confidence": "medium", "evidence": "negative_integer_return"}
    result = review_source(source, infer_candidates=[candidate])
    assert result["summary"]["count"] == 1
    finding = result["findings"][0]
    assert finding["severity"] == "low"
    assert finding["contract"]["source"] == "infer_candidate"
    assert "需人工确认" in finding["message"]


def test_checked_medium_infer_candidate_is_not_reported():
    source = "int f(const char *path) {\n    int rc = inferred_api(path);\n    if (rc < 0) { return rc; }\n    return 0;\n}"
    result = review_source(source, infer_candidates=[{"callee": "inferred_api", "confidence": "medium"}])
    assert result["summary"]["count"] == 0


def test_low_infer_candidate_does_not_enable_review():
    result = review_source("rc = inferred_api(path)", infer_candidates=[{"callee": "inferred_api", "confidence": "low"}])
    assert result["summary"]["count"] == 0
