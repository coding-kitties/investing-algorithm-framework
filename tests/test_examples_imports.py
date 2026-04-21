import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestExampleImports(TestCase):
    def test_open_example_does_not_fail_with_package_import_error(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "examples/open.py"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertNotIn(
            "ModuleNotFoundError: No module named 'investing_algorithm_framework'",
            result.stderr,
        )
