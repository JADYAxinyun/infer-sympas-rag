import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from diff_review import review_diff


def test_review_added_lines():
    diff = "diff --git a/config.py b/config.py\n+++ b/config.py\n@@ -1,2 +1,3 @@\n+    ret = load_config(path)\n+    continue_running()\n"
    result = review_diff(diff)
    assert result["summary"]["count"] == 1
    assert result["findings"][0]["file"] == "config.py"
