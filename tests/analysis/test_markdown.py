import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from investing_algorithm_framework.app.app import _apply_study_to_backtests
from investing_algorithm_framework.domain.backtesting.study import Study
from investing_algorithm_framework.analysis.markdown import (
    _run_matches,
    create_backtest_metrics_table,
    create_markdown_table,
    show_backtest_runs,
    show_backtest_summaries,
    show_trade_insights,
)
from investing_algorithm_framework.domain import (
    Backtest,
    BacktestDateRange,
    BacktestMetrics,
    BacktestRun,
    BacktestWindow,
)


class TestCreateMarkdownTable(unittest.TestCase):
    """Tests for the create_markdown_table function."""

    def test_empty_list_returns_no_data_message(self):
        """Test that an empty list returns a 'No Data' message."""
        result = create_markdown_table([])
        self.assertIn("No Data Available", result)
        self.assertIn("No records found", result)

    def test_none_returns_no_data_message(self):
        """Test that None-like empty data returns a 'No Data' message."""
        result = create_markdown_table([])
        self.assertIn("No Data Available", result)

    def test_single_dict_row(self):
        """Test table creation with a single dictionary row."""
        data = [{"name": "Alice", "age": 30}]
        result = create_markdown_table(data)

        # Check header
        self.assertIn("Name", result)
        self.assertIn("Age", result)

        # Check data
        self.assertIn("Alice", result)
        self.assertIn("30", result)

        # Check structure (3 lines: header, separator, data)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_multiple_dict_rows(self):
        """Test table creation with multiple dictionary rows."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35}
        ]
        result = create_markdown_table(data)

        # Check all names present
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("Charlie", result)

        # Check structure (5 lines: header, separator, 3 data rows)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 5)

    def test_float_formatting(self):
        """Test that floats are formatted with 2 decimal places."""
        data = [{"value": 3.14159}]
        result = create_markdown_table(data)
        self.assertIn("3.14", result)
        self.assertNotIn("3.14159", result)

    def test_none_value_shows_na(self):
        """Test that None values are displayed as 'N/A'."""
        data = [{"name": "Alice", "score": None}]
        result = create_markdown_table(data)
        self.assertIn("N/A", result)

    def test_header_titles_formatted(self):
        """Test that header titles have underscores replaced and are titled."""
        data = [{"first_name": "Alice", "last_name": "Smith"}]
        result = create_markdown_table(data)
        self.assertIn("First Name", result)
        self.assertIn("Last Name", result)

    def test_column_widths_accommodate_long_values(self):
        """Test that columns are wide enough for long values."""
        data = [
            {"name": "A", "description": "Short"},
            {"name": "B", "description": "This is a very long description"}
        ]
        result = create_markdown_table(data)

        # The column width should accommodate the longest value
        lines = result.strip().split("\n")

        # All lines should have the same structure
        for line in lines:
            self.assertTrue(line.startswith("|"))
            self.assertTrue(line.endswith("|"))

    def test_column_widths_accommodate_long_headers(self):
        """Test that columns are wide enough for long headers."""
        data = [{"very_long_column_name": "x"}]
        result = create_markdown_table(data)

        # Header should be fully visible
        self.assertIn("Very Long Column Name", result)

    def test_separator_line_matches_column_widths(self):
        """Test that separator line has correct dashes for each column."""
        data = [{"name": "Alice", "age": 30}]
        result = create_markdown_table(data)

        lines = result.strip().split("\n")
        separator = lines[1]

        # Separator should only contain |, -, and spaces
        for char in separator:
            self.assertIn(char, "|- ")

    def test_integer_values(self):
        """Test that integer values are converted to strings."""
        data = [{"count": 42, "total": 100}]
        result = create_markdown_table(data)
        self.assertIn("42", result)
        self.assertIn("100", result)

    def test_boolean_values(self):
        """Test that boolean values are converted to strings."""
        data = [{"active": True, "deleted": False}]
        result = create_markdown_table(data)
        self.assertIn("True", result)
        self.assertIn("False", result)

    def test_string_values(self):
        """Test that string values are preserved."""
        data = [{"message": "Hello, World!"}]
        result = create_markdown_table(data)
        self.assertIn("Hello, World!", result)

    def test_mixed_types(self):
        """Test table with various data types."""
        data = [{
            "name": "Test",
            "count": 5,
            "ratio": 0.75,
            "active": True,
            "notes": None
        }]
        result = create_markdown_table(data)

        self.assertIn("Test", result)
        self.assertIn("5", result)
        self.assertIn("0.75", result)
        self.assertIn("True", result)
        self.assertIn("N/A", result)

    def test_with_dataclass_objects(self):
        """Test table creation with dataclass objects."""
        @dataclass
        class Person:
            name: str
            age: int

        data = [Person(name="Alice", age=30), Person(name="Bob", age=25)]
        result = create_markdown_table(data)

        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("30", result)
        self.assertIn("25", result)

    def test_with_regular_objects(self):
        """Test table creation with regular class objects."""
        class Item:
            def __init__(self, id, value):
                self.id = id
                self.value = value

        data = [Item(1, "first"), Item(2, "second")]
        result = create_markdown_table(data)

        self.assertIn("1", result)
        self.assertIn("2", result)
        self.assertIn("first", result)
        self.assertIn("second", result)

    def test_evenly_spaced_columns(self):
        """Test that all rows have consistently spaced columns."""
        data = [
            {"short": "a", "medium": "hello", "long": "this is longer"},
            {"short": "bb", "medium": "hi", "long": "short"}
        ]
        result = create_markdown_table(data)
        lines = result.strip().split("\n")

        # Extract column positions from separator line
        separator = lines[1]
        pipe_positions = [i for i, c in enumerate(separator) if c == '|']

        # All lines should have pipes at the same positions
        for line in lines:
            line_pipes = [i for i, c in enumerate(line) if c == '|']
            self.assertEqual(pipe_positions, line_pipes)

    def test_empty_string_values(self):
        """Test that empty strings are handled correctly."""
        data = [{"name": "", "value": "test"}]
        result = create_markdown_table(data)

        # Should still create a valid table
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_numeric_string_values(self):
        """Test that numeric strings are preserved as strings."""
        data = [{"code": "12345", "zip": "01onal"}]
        result = create_markdown_table(data)
        self.assertIn("12345", result)


class TestShowTradeInsights(unittest.TestCase):
    def test_accepts_backtest_list_returned_by_run_backtest(self):
        date_range = BacktestDateRange(
            start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2022, 12, 31, tzinfo=timezone.utc),
        )
        run = BacktestRun(
            backtest_window=BacktestWindow(train_range=date_range),
        )
        run.backtest_metrics = BacktestMetrics(
            backtest_window=run.backtest_window,
            initial_unallocated=10_000,
            final_value=11_800,
            total_net_gain=1_800,
            total_net_gain_percentage=0.18,
            cagr=0.1853,
            sharpe_ratio=0.54,
            sortino_ratio=0.75,
            max_drawdown=0.1701,
            win_rate=0.4661,
            number_of_trades=120,
            number_of_trades_closed=118,
            number_of_positive_trades=55,
            percentage_positive_trades=46.61,
            number_of_negative_trades=63,
            percentage_negative_trades=53.39,
            number_of_long_trades=80,
            number_of_long_trades_closed=79,
            number_of_winning_long_trades=40,
            number_of_losing_long_trades=39,
            long_win_rate=40 / 79,
            number_of_short_trades=40,
            number_of_short_trades_closed=39,
            number_of_winning_short_trades=15,
            number_of_losing_short_trades=24,
            short_win_rate=15 / 39,
        )
        backtest = Backtest(
            algorithm_id="visualization_strategy",
            vector_runs=[run],
            study_name="visualization_study",
        )
        visualization_window = BacktestWindow(
            name="visualization_window",
            train_range=date_range,
        )

        _apply_study_to_backtests(
            [backtest],
            Study(
                name="visualization_study",
                backtest_windows=[visualization_window],
            ),
            [],
            None,
        )

        result = show_trade_insights(
            [backtest],
            study_name="visualization_study",
            window_name="visualization_window",
        )

        self.assertIs(run.backtest_window, visualization_window)
        self.assertIs(
            run.backtest_metrics.backtest_window, visualization_window
        )
        self.assertIn("Trade Insights", result)
        self.assertIn("visualization_window", result)
        self.assertIn("Backtest Run Metrics", result)
        self.assertIn("| Total Return | +18.00% |", result)
        self.assertIn("| Sharpe Ratio | 0.54 |", result)
        self.assertIn("| Winning Trades | 55 (46.61%) |", result)
        self.assertIn("| Long Trades | 80 |", result)
        self.assertIn("| Long Win Rate | 50.63% |", result)
        self.assertIn("| Short Trades | 40 |", result)
        self.assertIn("| Short Win Rate | 38.46% |", result)
        self.assertNotIn("(55, 46.61)", result)


class TestBacktestTableHeadings(unittest.TestCase):
    @patch(
        "investing_algorithm_framework.analysis.markdown."
        "create_backtest_metrics_table",
        return_value="table",
    )
    def test_summary_heading_includes_selected_study(self, _mock_table):
        study = type("Study", (), {"name": "in_sample_param_sweep"})()

        result = show_backtest_summaries([], study=study)

        self.assertTrue(result.startswith(
            "## Backtest Summaries in_sample_param_sweep\n"
        ))
        self.assertNotIn("- **Study:**", result)

    @patch(
        "investing_algorithm_framework.analysis.markdown."
        "_count_matching_runs",
        return_value=26,
    )
    @patch(
        "investing_algorithm_framework.analysis.markdown."
        "create_backtest_metrics_table",
        return_value="table",
    )
    def test_runs_heading_includes_selected_study_and_window(
        self, mock_table, _mock_count
    ):
        study = type("Study", (), {"name": "in_sample_param_sweep"})()
        window = type("Window", (), {"name": "window_1"})()

        result = show_backtest_runs(
            [], study=study, run=window, page=2, page_size=10
        )

        self.assertTrue(result.startswith(
            "## Backtest Runs in_sample_param_sweep window_1\n"
        ))
        self.assertNotIn("- **Study:**", result)
        self.assertNotIn("- **Run:**", result)
        self.assertIn("- **Page:** 2 of 3 (26 runs; 10 per page)", result)
        self.assertEqual(mock_table.call_args.kwargs["row_offset"], 10)
        self.assertEqual(mock_table.call_args.kwargs["row_limit"], 10)


class TestBacktestRunWindowMatching(unittest.TestCase):
    def test_parent_window_matches_test_run_by_window_name(self):
        train_range = BacktestDateRange(
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2022, 6, 1, tzinfo=timezone.utc),
            name="train_window_1",
        )
        test_range = BacktestDateRange(
            datetime(2022, 7, 1, tzinfo=timezone.utc),
            datetime(2022, 12, 1, tzinfo=timezone.utc),
            name="test_window_1",
        )
        window = BacktestWindow(
            train_range=train_range,
            test_range=test_range,
            name="window_1",
        )
        run = BacktestRun(backtest_window=window)

        self.assertTrue(_run_matches(run, window))
        self.assertTrue(_run_matches(run, "window_1"))
        self.assertFalse(_run_matches(run, train_range))

    def test_parent_window_filter_renders_window_column(self):
        train_range = BacktestDateRange(
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2022, 6, 1, tzinfo=timezone.utc),
            name="train_window_1",
        )
        test_range = BacktestDateRange(
            datetime(2022, 7, 1, tzinfo=timezone.utc),
            datetime(2022, 12, 1, tzinfo=timezone.utc),
            name="test_window_1",
        )
        window = BacktestWindow(
            train_range=train_range,
            test_range=test_range,
            name="window_1",
        )
        run = BacktestRun(
            backtest_window=window,
            backtest_metrics=BacktestMetrics(backtest_window=window),
        )

        class Result:
            algorithm_id = "strategy"

            @staticmethod
            def engines():
                return ["vector"]

            @staticmethod
            def get_runs(_engine):
                return [run]

        table = create_backtest_metrics_table(
            [Result()], level="run", window=[window]
        )

        self.assertIn("Window", table)
        self.assertIn("window_1", table)
        self.assertNotIn("test_window_1", table)


if __name__ == "__main__":
    unittest.main()
