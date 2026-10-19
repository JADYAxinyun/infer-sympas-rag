"""Exercise persisted summaries and caller invalidation in one Infer database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from query_slice import read_slices


@unittest.skipUnless(os.environ.get("INFER_BIN"), "requires a built Infer with SymPas")
class SummaryCacheTest(unittest.TestCase):
    def test_warm_analysis_and_changed_callee(self):
        with tempfile.TemporaryDirectory(prefix="sympas-cache-") as tmp:
            root = Path(tmp)
            source = root / "cache.c"
            out = root / "out"
            changed_files = root / "changed.txt"
            changed_files.write_text(str(source) + "\n")
            source.write_text("int cache_leaf(int a, int b) { return a; }\n"
                              "int cache_top(int a, int b) { return cache_leaf(a, b); }\n")
            base = [os.environ["INFER_BIN"], "--sympas-only", "--results-dir", str(out)]

            def run(*args):
                result = subprocess.run(base + list(args), cwd=root, capture_output=True,
                                        text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            def summaries():
                run("report")
                slices = read_slices(json.loads((out / "report.json").read_text()))
                return {item["procedure"]: item["procedure_summary"]["return_dependencies"]
                        for item in slices}

            run("capture", "--", "clang", "-c", str(source), "-o", str(root / "cache.o"))
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed_files))
            cold = summaries()
            self.assertEqual(cold["cache_top"], ["formal[0]"])
            changed_files.write_text("")
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed_files))
            self.assertEqual(summaries(), cold)
            source.write_text(source.read_text().replace("return a;", "return b;"))
            changed_files.write_text(str(source) + "\n")
            run("capture", "--continue", "--", "clang", "-c", str(source), "-o", str(root / "cache.o"))
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed_files))
            changed = summaries()
            self.assertEqual(changed["cache_leaf"], ["formal[1]"])
            self.assertEqual(changed["cache_top"], ["formal[1]"])


if __name__ == "__main__":
    unittest.main()
