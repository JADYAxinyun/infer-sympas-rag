import os
import unittest

from evaluate_symbolic import evaluate, ROOT


@unittest.skipUnless(os.environ.get("INFER_BIN"), "requires built Infer with heap summaries")
class HeapSummaryTest(unittest.TestCase):
    def test_factory_return_and_cross_procedure_memory(self):
        result = evaluate(os.environ["INFER_BIN"], ROOT / "tests/interprocedural/heap_summary.c", {})
        slices = result["actual_slices"]
        make = slices["heap_make"]["procedure_summary"]
        self.assertTrue(any(alias.startswith("heap:") for alias in make["return_aliases"]))
        self.assertTrue(any(out["target"].startswith("heap:") and "formal[0]" in out["dependencies"]
                            for out in make["outputs"]))
        self.assertEqual(slices["heap_factory_read"]["procedure_summary"]["return_dependencies"], ["formal[0]"])
        for procedure in ("heap_entry", "heap_factory_twice"):
            self.assertEqual(slices[procedure]["procedure_summary"]["return_dependencies"],
                             ["formal[0]", "formal[1]"])
        self.assertEqual(slices["heap_factory_twice"]["analysis_status"], "partial")

    def test_pointer_valued_output_preserves_aliases(self):
        result = evaluate(os.environ["INFER_BIN"], ROOT / "tests/interprocedural/heap_summary.c", {})
        slices = result["actual_slices"]
        bind = slices["heap_bind"]["procedure_summary"]
        output = next(item for item in bind["outputs"] if item["target"] == "memory(formal[0])")
        self.assertIn("memory(formal[1])", output["aliases"])
        self.assertEqual(slices["heap_bound_read"]["procedure_summary"]["return_dependencies"], ["formal[0]"])

    def test_unknown_pointer_read_retains_tracked_memory(self):
        result = evaluate(os.environ["INFER_BIN"], ROOT / "tests/interprocedural/heap_summary.c", {})
        evidence = result["actual_slices"]["heap_unknown_read"]
        self.assertIn("formal[0]", evidence["procedure_summary"]["return_dependencies"])
        self.assertTrue(any(item["status"] == "unresolved" for item in evidence["alias_evidence"]))
