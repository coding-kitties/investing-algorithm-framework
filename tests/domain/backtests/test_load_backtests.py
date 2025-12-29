import logging
import unittest
from pathlib import Path

from investing_algorithm_framework.domain.backtesting.backtest import Backtest
from investing_algorithm_framework.domain.backtesting.backtest_utils import (
    load_backtests_from_directory
)


class TestLoadBacktests(unittest.TestCase):
    """Test loading backtests from the test resources directory."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with path to test backtest data."""
        cls.test_resources_path = Path(__file__).parent.parent.parent / "resources"
        cls.backtests_path = cls.test_resources_path / "backtest_reports_for_testing"

        # Set up logging to see error messages during tests
        logging.basicConfig(level=logging.DEBUG)

    def test_backtests_directory_exists(self):
        """Test that the test backtests directory exists."""
        self.assertTrue(self.backtests_path.exists(),
                       f"Backtests directory should exist at {self.backtests_path}")
        self.assertTrue(self.backtests_path.is_dir(),
                       f"Backtests path should be a directory: {self.backtests_path}")

    def test_find_all_backtest_directories(self):
        """Test finding all individual backtest directories."""
        backtest_dirs = []

        for item in self.backtests_path.iterdir():
            if item.is_dir():
                backtest_dirs.append(item)

        self.assertGreater(len(backtest_dirs), 0,
                          "Should find at least one backtest directory")

        print(f"Found {len(backtest_dirs)} backtest directories:")
        for dir_path in backtest_dirs:
            print(f"  - {dir_path.name}")

    def test_load_all_backtests_without_errors(self):
        """
        Test loading all backtests from the directory without errors.
        """
        try:
            print(self.backtests_path)
            backtests = load_backtests_from_directory(str(self.backtests_path))

            self.assertIsInstance(
                backtests, list,"load_backtests_from_directory should return a list"
            )

            print(f"Successfully loaded {len(backtests)} backtests")

            # Verify that we got some backtests
            self.assertGreater(len(backtests), 0,
                             "Should load at least one backtest")

            # Verify all items are Backtest instances
            for i, backtest in enumerate(backtests):
                self.assertIsInstance(backtest, Backtest,
                                    f"Item {i} should be a Backtest instance")

        except Exception as e:
            self.fail(f"Failed to load backtests: {e}")
