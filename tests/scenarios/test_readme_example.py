"""
Test the README example implementation to ensure it works correctly.

This test dynamically extracts the Python code from README.md and executes it
to verify that the documented examples actually work. This ensures the README
stays in sync with the actual codebase.
"""
from investing_algorithm_framework import BacktestRunConfiguration
import os
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    DATA_DIRECTORY,
    RESOURCE_DIRECTORY,
    SnapshotInterval,
    Study,
    Universe,
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

    This selects the recommended declarative RSIConfluenceStrategy example.

    Args:
        readme_path: Path to the README.md file

    Returns:
        The main example code as a string
    """
    code_blocks = extract_python_code_blocks_from_readme(readme_path)

    for block in code_blocks:
        if 'class RSIConfluenceStrategy(' in block:
            return block

    raise ValueError(
        "Could not find the RSIConfluenceStrategy example in README.md"
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
        self.assertIn('RSIConfluenceStrategy', main_example)
        self.assertIn('confluence_cards', main_example)
        self.assertIn('indicator_configs', main_example)

    def test_readme_strategy_class_is_valid_python(self):
        """The RSIConfluenceStrategy code from README compiles."""
        main_example = extract_main_example_from_readme(self.readme_path)

        try:
            compile(main_example, '<readme>', 'exec')
        except SyntaxError as e:
            self.fail(f"README example has syntax error: {e}")

    def test_readme_strategy_uses_take_profits(self):
        """The README example demonstrates TakeProfitRule usage."""
        main_example = extract_main_example_from_readme(self.readme_path)
        self.assertIn('TakeProfitRule', main_example)
        self.assertIn('take_profits', main_example)

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

        self.assertIn('RSIConfluenceStrategy', namespace)
        cls = namespace['RSIConfluenceStrategy']

        # Verify class attributes
        self.assertTrue(hasattr(cls, 'generate_signals'))
        self.assertTrue(hasattr(cls, 'generate_signal_series'))
        self.assertTrue(hasattr(cls, 'confluence_cards'))
        self.assertTrue(hasattr(cls, 'indicator_configs'))
        self.assertTrue(hasattr(cls, 'take_profits'))
        self.assertTrue(hasattr(cls, 'stop_losses'))
        self.assertTrue(hasattr(cls, 'position_sizes'))
        self.assertTrue(hasattr(cls, 'data_sources'))

        self.assertGreater(len(cls.confluence_cards), 0)
        self.assertGreater(len(cls.indicator_configs), 0)
        self.assertGreater(len(cls.take_profits), 0)
        # Verify stop losses are defined
        self.assertGreater(len(cls.stop_losses), 0)

    def test_readme_strategy_runs_fast_vector_backtest_with_offline_data(self):
        """The README strategy runs using only compact offline test data."""
        main_example = extract_main_example_from_readme(self.readme_path)
        namespace = {}
        exec(main_example, namespace)
        strategy_class = namespace['RSIConfluenceStrategy']

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
        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            initial_capital=1000,
            risk_free_rate=0.027,
            backtest_windows=[
                BacktestWindow(train_range=BacktestDateRange(
                    start_date=datetime(2023, 9, 1, tzinfo=timezone.utc),
                    end_date=datetime(2023, 11, 15, tzinfo=timezone.utc),
                ))
            ],
            engines=[BacktestEngine.VECTOR],
        )
        backtests = app.run_backtest(
            strategy=strategy,
            study=study,
            run_configuration=BacktestRunConfiguration(
                snapshot_interval=SnapshotInterval.DAILY,
                use_checkpoints=False,
            ),
        )
        backtest = next(backtests.iter_backtests())

        self.assertIsNotNone(backtest)
        self.assertEqual(len(backtest.get_all_backtest_runs()), 1)
        self.assertEqual(len(backtest.get_all_backtest_metrics()), 1)


if __name__ == "__main__":
    unittest.main()
