import os
import unittest

from evaluate_symbolic import evaluate, ROOT


@unittest.skipUnless(os.environ.get("INFER_BIN"), "requires built Infer with SCC solver")
class SCCFixpointTest(unittest.TestCase):
    def test_fixedpoint_metadata_and_definition_order_independence(self):
        summaries = []
        for filename in ("recursive_precision.c", "recursive_precision_reordered.c"):
            result = evaluate(os.environ["INFER_BIN"], ROOT / "tests/interprocedural" / filename, {})
            summaries.append({name: value["procedure_summary"]
                              for name, value in result["actual_slices"].items()})
        for name in ("rec_first", "rec_left", "rec_right"):
            first, second = (table[name] for table in summaries)
            self.assertEqual(first["return_dependencies"], second["return_dependencies"])
            self.assertEqual(first["fixed_point"], second["fixed_point"])
            fixed = first["fixed_point"]
            self.assertEqual(fixed["status"], "converged")
            self.assertEqual(fixed["mode"], "synchronous_scc_iteration")
            self.assertGreater(fixed["iterations"], 1)
            self.assertLess(fixed["iterations"], 20)
            self.assertIn(name, fixed["members"])
        self.assertEqual(summaries[0]["rec_left"]["fixed_point"]["members"], ["rec_left", "rec_right"])
        self.assertEqual(summaries[0]["rec_entry"]["return_dependencies"], ["formal[0]", "formal[2]"])


if __name__ == "__main__":
    unittest.main()
