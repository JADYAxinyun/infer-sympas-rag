import os
from pathlib import Path
import tempfile
import unittest

from evaluate_symbolic import evaluate


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
