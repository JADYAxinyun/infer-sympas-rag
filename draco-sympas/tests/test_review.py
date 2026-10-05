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
