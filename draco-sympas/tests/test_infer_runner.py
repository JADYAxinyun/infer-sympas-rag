from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from infer_runner import run_infer


def test_missing_report_is_explicit(tmp_path):
    result = run_infer(tmp_path, ["true"], infer_bin="/not/a/real/infer")
    assert result["ok"] is False
    assert result["findings"] == []
