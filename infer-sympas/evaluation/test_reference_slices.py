import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
import sys

from evaluate_reference_slices import compare, run_reference, statement_map, ROOT


class ReferenceContractTest(unittest.TestCase):
    def test_empty_reference_manifest_is_rejected_before_analysis(self):
        manifest = json.loads(Path(__file__).with_name("reference_slices.json").read_text())
        manifest["cases"] = []
        with patch("evaluate_reference_slices.evaluate") as analyze:
            with self.assertRaises(ValueError):
                run_reference("not_executed", manifest)
            analyze.assert_not_called()

    def test_unsupported_criterion_is_not_silently_reinterpreted(self):
        manifest = json.loads(Path(__file__).with_name("reference_slices.json").read_text())
        manifest["cases"][0]["criterion"] = {"type": "variable", "variable": "a", "line": 4}
        with patch("evaluate_reference_slices.evaluate") as analyze:
            with self.assertRaises(ValueError):
                run_reference("not_executed", manifest)
            analyze.assert_not_called()

    def test_cli_execution_failure_is_structured_and_nonzero(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("evaluate_reference_slices.py")),
                                 "--infer", str(ROOT / "missing-infer-for-failure-test")],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        evidence = json.loads(result.stdout)
        self.assertFalse(evidence["ok"])
        self.assertEqual(evidence["analysis_status"], "failed")
        self.assertEqual(evidence["metrics_status"], "not_computed")

    def test_missing_and_extra_statements_are_distinguished(self):
        result = compare(["write", "return"], ["return", "unrelated"], "exact")
        self.assertEqual(result["missing"], ["write"])
        self.assertEqual(result["extra"], ["unrelated"])
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)
        self.assertFalse(result["ok"])

    def test_conservative_mode_still_rejects_missing_dependencies(self):
        self.assertFalse(compare(["write", "return"], ["return"], "conservative")["ok"])
        self.assertTrue(compare(["return"], ["return", "extra"], "conservative")["ok"])

    def test_reference_labels_are_present_and_nonempty(self):
        manifest = json.loads(Path(__file__).with_name("reference_slices.json").read_text())
        labels = statement_map(ROOT / manifest["source"])
        for case in manifest["cases"]:
            self.assertTrue(case["reference"])
            self.assertTrue(set(case["reference"]) <= labels.keys())

    @unittest.skipUnless(os.environ.get("INFER_BIN"), "requires built Infer with heap locations")
    def test_real_sil_matches_pre_authored_references(self):
        manifest = json.loads(Path(__file__).with_name("reference_slices.json").read_text())
        result = run_reference(os.environ["INFER_BIN"], manifest)
        self.assertEqual(result["total"], len(manifest["cases"]))
        for case in result["cases"]:
            with self.subTest(procedure=case["procedure"]):
                self.assertTrue(case["ok"], case)
