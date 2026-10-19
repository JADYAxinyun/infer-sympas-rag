"""Criteria integration tests against real SIL snapshots, not a mock slicer."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from query_slice import select
from evaluate_symbolic import evaluate, ROOT


@unittest.skipUnless(os.environ.get("INFER_BIN"), "requires a built Infer with SymPas")
class CriteriaIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = evaluate(os.environ["INFER_BIN"],
                          ROOT / "tests/interprocedural/symbolic_outputs.c", {})
        cls.slices = list(result["actual_slices"].values())

    def check_criterion(self, kind, **fields):
        results = select(self.slices, {"type": kind, "procedure": "sym_two_calls", **fields})
        self.assertTrue(results)
        for result in results:
            self.assertNotEqual(result["analysis_status"], "unsupported")
            self.assertEqual(result["data_dependencies"], ["formal[0]"])
            self.assertTrue(result["source_locations"])
            self.assertFalse(any(source["procedure"] == "sym_two_calls" and source["line"] == 7
                                 for source in result["source_locations"]))
        return results

    def test_return_value(self):
        self.check_criterion("return_value")

    def test_variable_definition(self):
        self.check_criterion("variable", variable="first", line=6)

    def test_call_site(self):
        self.check_criterion("call_site", line=6)

    def test_finding_variable(self):
        self.check_criterion("finding_variable", variable="first", line=6)

    def test_return_point(self):
        self.check_criterion("return_point", line=9)

    def test_file_location(self):
        self.check_criterion("file_location", line=6, column=17,
                             file="infer-sympas/tests/interprocedural/symbolic_outputs.c")

    def test_missing_location_is_explicit(self):
        result = select(self.slices, {"type": "file_location", "line": 999999})
        self.assertEqual(result[0]["analysis_status"], "unsupported")

    def test_missing_variable_is_rejected(self):
        with self.assertRaises(ValueError):
            select(self.slices, {"type": "variable"})

    def test_returned_pointer_summary_has_symbolic_target(self):
        procedure = next(value for value in self.slices if value["procedure"] == "sym_identity_pointer")
        self.assertEqual(procedure["procedure_summary"]["return_aliases"], ["memory(formal[0])"])

    def test_alias_evidence_distinguishes_confirmed_possible_and_unresolved(self):
        procedures = {value["procedure"]: value for value in self.slices}
        for name, status in (("sym_alias", "confirmed"), ("sym_may_alias", "possible"),
                             ("sym_unresolved_pointer", "unresolved")):
            self.assertIn(status, {item["status"] for item in procedures[name]["alias_evidence"]})


if __name__ == "__main__":
    unittest.main()
