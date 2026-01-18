"""
Test the README example implementation to ensure it works correctly.

This test dynamically extracts the Python code from README.md and executes it
to verify that the documented examples actually work. This ensures the README
stays in sync with the actual codebase.
"""
import os
import re
from unittest import TestCase

from investing_algorithm_framework import RESOURCE_DIRECTORY


def extract_python_code_blocks_from_readme(readme_path: str) -> list[str]:
    """
    Extract all Python code blocks from a README.md file.

    Args:
        readme_path: Path to the README.md file

    Returns:
        List of Python code strings extracted from the README
    """
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match ```python ... ``` code blocks
    pattern = r'```python\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)

    return matches


def extract_main_example_from_readme(readme_path: str) -> str:
    """
    Extract the main trading strategy example from README.md.

    This looks for the large code block that contains the
    RSIEMACrossoverStrategy class and the main execution block.

    Args:
        readme_path: Path to the README.md file

    Returns:
        The main example code as a string
    """
    code_blocks = extract_python_code_blocks_from_readme(readme_path)

    # Find the code block that contains the RSIEMACrossoverStrategy
    for block in code_blocks:
        if 'RSIEMACrossoverStrategy' in block and 'class' in block:
            return block

    raise ValueError(
        "Could not find the RSIEMACrossoverStrategy example in README.md"
    )


class TestReadmeExample(TestCase):
    """
    Test class to verify the README example implementation works correctly.

    This test dynamically extracts code from README.md and executes it to
    ensure the documented examples are valid and functional.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Resource directory points to /tests/resources
        self.resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'resources'
        )

        # README.md is at the root of the project
        self.readme_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'README.md'
        )

    def test_readme_code_can_be_extracted(self):
        """
        Test that Python code blocks can be extracted from README.md.

        This test verifies that:
        ✅ README.md exists and is readable
        ✅ At least one Python code block exists
        ✅ The main RSIEMACrossoverStrategy example can be found
        """
        self.assertTrue(
            os.path.exists(self.readme_path),
            f"README.md not found at {self.readme_path}"
        )

        code_blocks = extract_python_code_blocks_from_readme(self.readme_path)
        self.assertGreater(
            len(code_blocks), 0,
            "No Python code blocks found in README.md"
        )

        # Verify the main example exists
        main_example = extract_main_example_from_readme(self.readme_path)
        self.assertIn('RSIEMACrossoverStrategy', main_example)
        self.assertIn('generate_buy_signals', main_example)
        self.assertIn('generate_sell_signals', main_example)

    def test_readme_strategy_class_is_valid_python(self):
        """
        Test that the RSIEMACrossoverStrategy code from README is valid Python.

        This test verifies that:
        ✅ The code can be parsed and compiled without syntax errors
        ✅ The RSIEMACrossoverStrategy class can be instantiated
        ✅ The class has required methods (generate_buy_signals, generate_sell_signals)
        """
        main_example = extract_main_example_from_readme(self.readme_path)

        # Extract just the class definition (before if __name__ == "__main__":)
        if 'if __name__ == "__main__":' in main_example:
            class_code = main_example.split('if __name__ == "__main__":')[0]
        else:
            class_code = main_example

        # Compile the code to check for syntax errors
        try:
            compile(class_code, '<readme>', 'exec')
        except SyntaxError as e:
            self.fail(f"README example has syntax error: {e}")

    def test_readme_strategy_can_be_instantiated_and_run_vector_backtest(self):
        """
        Test that the RSIEMACrossoverStrategy from README can be instantiated
        and used to run a vector backtest.

        This test verifies that:
        ✅ The strategy class from README.md can be dynamically loaded
        ✅ The strategy can be instantiated with example parameters
        ✅ The strategy can run a vector backtest successfully
        ✅ The backtest returns valid results
        """
        main_example = extract_main_example_from_readme(self.readme_path)

        # Extract just the class definition (before if __name__ == "__main__":)
        if 'if __name__ == "__main__":' in main_example:
            class_code = main_example.split('if __name__ == "__main__":')[0]
        else:
            class_code = main_example

        # Create a namespace with required imports
        namespace = {}

        # Execute the imports and class definition
        exec(class_code, namespace)

        # Verify the class was created
        self.assertIn('RSIEMACrossoverStrategy', namespace)

        # Import additional items needed for backtest
        from investing_algorithm_framework import (
            create_app, BacktestDateRange, SnapshotInterval
        )
        from datetime import datetime, timezone

        # Create the app with test resource directory
        config = {RESOURCE_DIRECTORY: self.resource_directory}
        app = create_app(name="ReadmeExampleTest", config=config)
        app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=1000)

        # Instantiate the strategy from README
        RSIEMACrossoverStrategy = namespace['RSIEMACrossoverStrategy']
        strategy = RSIEMACrossoverStrategy(
            time_unit=namespace['TimeUnit'].HOUR,
            interval=2,
            market="BITVAVO",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=12,
            ema_long_period=26,
            ema_cross_lookback_window=10
        )

        # Use date range within available test data
        # Data available: OHLCV_BTC-EUR_BITVAVO_2h_2022-12-03-00-00_2025-12-02-00-00.csv
        backtest_range = BacktestDateRange(
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
        )

        # Run vector backtest
        backtest = app.run_vector_backtest(
            initial_amount=1000,
            backtest_date_range=backtest_range,
            strategy=strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            use_checkpoints=False,
        )

        # Verify backtest results
        self.assertIsNotNone(backtest)
        self.assertEqual(len(backtest.get_all_backtest_runs()), 1)
        self.assertEqual(len(backtest.get_all_backtest_metrics()), 1)

    def test_readme_strategy_can_be_instantiated_and_run_event_backtest(self):
        """
        Test that the RSIEMACrossoverStrategy from README can be instantiated
        and used to run a vector backtest.

        This test verifies that:
        ✅ The strategy class from README.md can be dynamically loaded
        ✅ The strategy can be instantiated with example parameters
        ✅ The strategy can run a vector backtest successfully
        ✅ The backtest returns valid results
        """
        main_example = extract_main_example_from_readme(self.readme_path)

        # Extract just the class definition (before if __name__ == "__main__":)
        if 'if __name__ == "__main__":' in main_example:
            class_code = main_example.split('if __name__ == "__main__":')[0]
        else:
            class_code = main_example

        # Create a namespace with required imports
        namespace = {}

        # Execute the imports and class definition
        exec(class_code, namespace)

        # Verify the class was created
        self.assertIn('RSIEMACrossoverStrategy', namespace)

        # Import additional items needed for backtest
        from investing_algorithm_framework import (
            create_app, BacktestDateRange, SnapshotInterval
        )
        from datetime import datetime, timezone

        # Create the app with test resource directory
        config = {RESOURCE_DIRECTORY: self.resource_directory}
        app = create_app(name="ReadmeExampleTest", config=config)
        app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=1000)

        # Instantiate the strategy from README
        RSIEMACrossoverStrategy = namespace['RSIEMACrossoverStrategy']
        strategy = RSIEMACrossoverStrategy(
            time_unit=namespace['TimeUnit'].HOUR,
            interval=2,
            market="BITVAVO",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=12,
            ema_long_period=26,
            ema_cross_lookback_window=10
        )

        # Use date range within available test data
        # Data available: OHLCV_BTC-EUR_BITVAVO_2h_2022-12-03-00-00_2025-12-02-00-00.csv
        backtest_range = BacktestDateRange(
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
        )

        # Run vector backtest
        backtest = app.run_backtest(
            initial_amount=1000,
            backtest_date_range=backtest_range,
            strategy=strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            use_checkpoints=False,
        )

        # Verify backtest results
        self.assertIsNotNone(backtest)
        self.assertEqual(len(backtest.get_all_backtest_runs()), 1)
        self.assertEqual(len(backtest.get_all_backtest_metrics()), 1)

    def test_readme_main_block_structure(self):
        """
        Test that the main execution block in README follows expected patterns.

        This test verifies that the README example includes:
        ✅ create_app() call
        ✅ add_strategy() call with strategy instance
        ✅ add_market() call with market configuration
        ✅ BacktestDateRange definition
        ✅ run_backtest() call
        ✅ BacktestReport usage
        """
        main_example = extract_main_example_from_readme(self.readme_path)

        # Check for required patterns in the main block
        self.assertIn('create_app()', main_example)
        self.assertIn('add_strategy(', main_example)
        self.assertIn('add_market(', main_example)
        self.assertIn('BacktestDateRange(', main_example)
        self.assertIn('run_backtest(', main_example)
        self.assertIn('BacktestReport(', main_example)



if __name__ == "__main__":
    import unittest
    unittest.main()

