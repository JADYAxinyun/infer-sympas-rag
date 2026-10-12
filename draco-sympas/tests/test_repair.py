import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1]))
from repair import propose_return_check


def test_repair_removes_unchecked_return_finding():
    source = "int f(const char *path) {\n    int ret = open_config(path);\n    continue_running();\n}\n"
    finding = {"rule": "unchecked_return_value", "line": 2, "variable": "ret"}
    patch = propose_return_check(source, finding)
    assert patch is not None
    assert "if (ret < 0)" in patch["source"]


def test_repair_rejects_unknown_rule():
    assert propose_return_check("x();\n", {"rule": "unknown", "line": 1}) is None
