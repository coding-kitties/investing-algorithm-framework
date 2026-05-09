"""
Test the README example implementation to ensure it works correctly.

This test dynamically extracts the Python code from README.md and executes it
to verify that the documented examples actually work. This ensures the README
stays in sync with the actual codebase.
"""
import os
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    DATA_DIRECTORY,
    RESOURCE_DIRECTORY,
    SnapshotInterval,
    create_app,
)


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


def prepare_readme_example_for_test(main_example: str) -> str:
    """Adapt the README strategy to the compact offline test fixture set."""
    return (
        main_example
        .replace('symbols = ["BTC", "ETH"]', 'symbols = ["BTC", "DOT"]')
        .replace(
            'identifier="ETH_ohlcv", symbol="ETH/EUR"',
            'identifier="DOT_ohlcv", symbol="DOT/EUR"',
        )
        .replace('symbol="ETH"', 'symbol="DOT"')
    )


class TestReadmeExample(TestCase):
    """
    Test class to verify the README example implementation works correctly.

    This test dynamically extracts code from README.md and executes it to
    ensure the documented examples are valid and functional.
    """

    def setUp(self):
        """Set up test fixtures."""
        # README.md is at the root of the project
        self.readme_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'README.md'
        )
        self.resource_directory = str(
            Path(__file__).parent.parent / 'resources'
        )

    def test_readme_code_can_be_extracted(self):
        """README.md exists and contains extractable Python code blocks."""
        self.assertTrue(
            os.path.exists(self.readme_path),
            f"README.md not found at {self.readme_path}"
        )

        code_blocks = extract_python_code_blocks_from_readme(self.readme_path)
        self.assertGreater(
            len(code_blocks), 0,
            "No Python code blocks found in README.md"
        )

        # Verify the main strategy example exists
        main_example = extract_main_example_from_readme(self.readme_path)
        self.assertIn('RSIEMACrossoverStrategy', main_example)
        self.assertIn('generate_buy_signals', main_example)
        self.assertIn('generate_sell_signals', main_example)

    def test_readme_strategy_class_is_valid_python(self):
        """The RSIEMACrossoverStrategy code from README compiles."""
        main_example = extract_main_example_from_readme(self.readme_path)

        try:
            compile(main_example, '<readme>', 'exec')
        except SyntaxError as e:
            self.fail(f"README example has syntax error: {e}")

    def test_readme_strategy_uses_scaling_rules(self):
        """The README example demonstrates ScalingRule usage."""
        main_example = extract_main_example_from_readme(self.readme_path)
        self.assertIn('ScalingRule', main_example)
        self.assertIn('scaling_rules', main_example)

    def test_readme_strategy_uses_stop_losses(self):
        """The README example demonstrates StopLossRule usage."""
        main_example = extract_main_example_from_readme(self.readme_path)
        self.assertIn('StopLossRule', main_example)
        self.assertIn('stop_losses', main_example)

    def test_readme_strategy_class_can_be_loaded(self):
        """The strategy class from README can be exec'd and inspected."""
        main_example = extract_main_example_from_readme(self.readme_path)

        namespace = {}
        exec(main_example, namespace)

        self.assertIn('RSIEMACrossoverStrategy', namespace)
        cls = namespace['RSIEMACrossoverStrategy']

        # Verify class attributes
        self.assertTrue(hasattr(cls, 'generate_buy_signals'))
        self.assertTrue(hasattr(cls, 'generate_sell_signals'))
        self.assertTrue(hasattr(cls, 'scaling_rules'))
        self.assertTrue(hasattr(cls, 'stop_losses'))
        self.assertTrue(hasattr(cls, 'position_sizes'))
        self.assertTrue(hasattr(cls, 'data_sources'))

        # Verify scaling rules are defined
        self.assertGreater(len(cls.scaling_rules), 0)
        # Verify stop losses are defined
        self.assertGreater(len(cls.stop_losses), 0)

    def test_readme_strategy_runs_fast_vector_backtest_with_offline_data(self):
        """The README strategy runs using only compact offline test data."""
        main_example = extract_main_example_from_readme(self.readme_path)
        class_code = prepare_readme_example_for_test(main_example)

        namespace = {}
        exec(class_code, namespace)
        strategy_class = namespace['RSIEMACrossoverStrategy']

        app = create_app(
            name="ReadmeExampleTest",
            config={
                RESOURCE_DIRECTORY: self.resource_directory,
                DATA_DIRECTORY: "test_data/ohlcv",
            },
        )
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )

        strategy = strategy_class(algorithm_id="readme-example-test")
        backtest = app.run_vector_backtest(
            initial_amount=1000,
            backtest_date_range=BacktestDateRange(
                start_date=datetime(2023, 9, 1, tzinfo=timezone.utc),
                end_date=datetime(2023, 11, 15, tzinfo=timezone.utc),
            ),
            strategy=strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            use_checkpoints=False,
        )

        self.assertIsNotNone(backtest)
        self.assertEqual(len(backtest.get_all_backtest_runs()), 1)
        self.assertEqual(len(backtest.get_all_backtest_metrics()), 1)


if __name__ == "__main__":
    unittest.main()
