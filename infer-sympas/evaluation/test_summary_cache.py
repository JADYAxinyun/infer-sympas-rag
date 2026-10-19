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
    def test_changed_scc_member_invalidates_unchanged_caller_across_files(self):
        with tempfile.TemporaryDirectory(prefix="sympas-scc-cache-") as tmp:
            root = Path(tmp)
            left, right, caller = (root / name for name in ("left.c", "right.c", "caller.c"))
            left.write_text("int cache_right(int,int,int);\n"
                            "int cache_left(int a,int b,int n) { if(n<=0) return a; "
                            "return cache_right(b,a,n-1); }\n")
            right.write_text("int cache_left(int,int,int);\n"
                             "int cache_right(int a,int b,int n) { if(n<=0) return b; "
                             "return cache_left(b,a,n-1); }\n")
            caller.write_text("int cache_left(int,int,int);\n"
                              "int cache_caller(int a,int b,int n) { return cache_left(a,b,n); }\n")
            out, changed = root / "out", root / "changed.txt"
            base = [os.environ["INFER_BIN"], "--sympas-only", "--results-dir", str(out)]

            def run(*args):
                result = subprocess.run(base + list(args), cwd=root, capture_output=True,
                                        text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            def caller_summary():
                run("report")
                values = read_slices(json.loads((out / "report.json").read_text()))
                return next(value["procedure_summary"]["return_dependencies"]
                            for value in values if value["procedure"] == "cache_caller")

            changed.write_text("\n".join(map(str, (left, right, caller))) + "\n")
            run("capture", "--", "clang", "-c", str(left), str(right), str(caller))
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed))
            self.assertEqual(caller_summary(), ["formal[0]", "formal[2]"])
            right.write_text(right.read_text().replace("return b;", "return a;"))
            changed.write_text(str(right) + "\n")
            run("capture", "--continue", "--", "clang", "-c", str(right))
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed), "--invalidate-only")
            # Request all captured roots after invalidation; --changed-files-index
            # alone schedules only changed-file roots in this Infer version.
            run("analyze", "--continue-analysis")
            self.assertEqual(caller_summary(), ["formal[0]", "formal[1]", "formal[2]"])
            left.write_text(left.read_text().replace("return a;", "return b;"))
            changed.write_text(str(left) + "\n")
            run("capture", "--continue", "--", "clang", "-c", str(left))
            run("analyze", "--incremental-analysis", "--changed-files-index", str(changed), "--invalidate-only")
            run("analyze", "--continue-analysis")
            self.assertEqual(caller_summary(), ["formal[1]", "formal[2]"])
            values = read_slices(json.loads((out / "report.json").read_text()))
            right_summary = next(value["procedure_summary"] for value in values
                                 if value["procedure"] == "cache_right")
            self.assertEqual(right_summary["return_dependencies"], ["formal[0]", "formal[2]"])

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
