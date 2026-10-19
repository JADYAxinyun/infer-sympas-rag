import os
from pathlib import Path
import tempfile
import unittest
import json
import subprocess
import sys

from evaluate_symbolic import evaluate

ROOT = Path(__file__).resolve().parents[1]


class CommandFailureTest(unittest.TestCase):
    def test_broken_report_emits_uniform_failed_slice(self):
        with tempfile.TemporaryDirectory(prefix="sympas-broken-report-") as tmp:
            report = Path(tmp) / "report.json"
            report.write_text("{")
            run = subprocess.run([sys.executable, str(ROOT / "query_slice.py"), str(report)],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 2)
            result = json.loads(run.stdout)[0]
            self.assertEqual(result["analysis_status"], "failed")
            self.assertIn("source_locations", result)

    def test_missing_infer_emits_failed_evaluation(self):
        run = subprocess.run([sys.executable, str(ROOT / "evaluation/evaluate_symbolic.py"),
                              "--infer", "/nonexistent-sympas-test/infer"],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 1)
        result = json.loads(run.stdout)
        self.assertEqual(result["environment"]["version_status"], "failed")
        self.assertTrue(all(case["analysis_status"] == "failed" for case in result["cases"]))

    def test_empty_manifest_cannot_pass(self):
        with tempfile.TemporaryDirectory(prefix="sympas-empty-manifest-") as tmp:
            manifest = Path(tmp) / "empty.json"
            manifest.write_text("[]")
            run = subprocess.run([sys.executable, str(ROOT / "evaluation/evaluate_symbolic.py"),
                                  "--infer", "infer", "--manifest", str(manifest)],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 2)


@unittest.skipUnless(os.environ.get("INFER_BIN"), "requires a built Infer")
class AnalysisFailureTest(unittest.TestCase):
    def test_invalid_c_does_not_become_an_empty_successful_slice(self):
        with tempfile.TemporaryDirectory(prefix="sympas-invalid-") as tmp:
            source = Path(tmp) / "invalid.c"
            source.write_text("int invalid( { return 0; }\n")
            with self.assertRaises(RuntimeError):
                evaluate(os.environ["INFER_BIN"], source, {})


if __name__ == "__main__":
    unittest.main()
