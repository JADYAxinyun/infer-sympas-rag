import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from report import render_markdown


def test_render_report():
    text = render_markdown({"review": {"findings": [{"rule": "unchecked_return_value", "line": 2}]}})
    assert "unchecked_return_value" in text
    assert "Code Review Report" in text
