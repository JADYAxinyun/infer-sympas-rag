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

    def test_variable_at_use_and_after_overwrite(self):
        raw = evaluate(os.environ["INFER_BIN"], ROOT / "tests/intraprocedural/program_points.c", {})
        slices = list(raw["actual_slices"].values())
        for kind in ("variable", "finding_variable"):
            for line, dependency in ((4, "formal[0]"), (6, "formal[1]")):
                with self.subTest(kind=kind, line=line):
                    results = select(slices, {"type": kind, "procedure": "point_value",
                                             "variable": "selected", "line": line})
                    self.assertTrue(all(result["analysis_status"] != "unsupported" for result in results))
                    self.assertTrue(all(result["data_dependencies"] == [dependency] for result in results))
                    self.assertTrue(all(result["criterion"]["state_position"] == "after_instruction"
                                        for result in results))

    def test_variable_point_retains_path_control_and_rejects_missing_variable(self):
        raw = evaluate(os.environ["INFER_BIN"], ROOT / "tests/intraprocedural/program_points.c", {})
        slices = list(raw["actual_slices"].values())
        results = select(slices, {"type": "variable", "procedure": "point_control",
                                 "variable": "selected", "line": 12})
        self.assertTrue(all(result["data_dependencies"] == ["formal[0]", "formal[1]"]
                            for result in results))
        self.assertTrue(all(any(control["location"]["line"] == 11
                                for control in result["control_dependencies"]) for result in results))
        missing = select(slices, {"type": "variable", "procedure": "point_control",
                                 "variable": "not_declared", "line": 12})
        self.assertEqual(missing[0]["analysis_status"], "unsupported")

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
        self.assertTrue({"procedure", "criterion", "data_dependencies", "control_dependencies",
                         "procedure_summary", "call_chain", "source_locations", "precision"}
                        <= result[0].keys())

    def test_return_value_honors_file_filter(self):
        result = select(self.slices, {"type": "return_value", "procedure": "sym_two_calls",
                                     "file": "not-the-captured-file.c"})
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
