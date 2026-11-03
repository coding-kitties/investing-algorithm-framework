import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

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
    BacktestIndex,
    BacktestDateRange,
    BacktestMetrics,
    BacktestRun,
    BacktestSummaryMetrics,
    BacktestWindow,
    OperationalException,
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
    def test_summary_defaults_use_explicit_window_metric_labels(self):
        summary = BacktestSummaryMetrics(
            aggregation_semantics_version=2,
            aggregation_mode="independent_windows",
            capital_weighted_window_return=0.1259,
            median_window_return=0.20,
            worst_window_return=-0.10,
            best_window_return=0.30,
            worst_window_max_drawdown=0.40,
            duration_weighted_mean_window_cagr=3.95,
            portfolio_cagr=None,
            number_of_profitable_windows=2,
            window_count_evaluated=3,
            window_count_expected=3,
            mean_window_duration_days=60.333,
        )

        class Result:
            algorithm_id = "strategy"

            @staticmethod
            def engines():
                return ["vector"]

            @staticmethod
            def get_summary(_engine):
                return summary

        table = create_backtest_metrics_table([Result()])

        self.assertIn("Capital-Weighted Window Return %", table)
        self.assertIn("Worst-Window Max DD %", table)
        self.assertIn("Duration-Weighted Mean Window CAGR %", table)
        self.assertIn("Portfolio CAGR %", table)
        self.assertIn("N/A", table)
        self.assertIn("Mean Window Duration (days)", table)
        self.assertNotIn("Avg Window Duration", table)

    def test_unversioned_summary_uses_explicit_legacy_labels(self):
        summary = BacktestSummaryMetrics(
            total_net_gain_percentage=0.10,
            cagr=0.50,
            sharpe_ratio=1.20,
            max_drawdown=0.05,
            number_of_windows=2,
        )

        class Result:
            algorithm_id = "legacy-strategy"

            @staticmethod
            def engines():
                return ["vector"]

            @staticmethod
            def get_summary(_engine):
                return summary

        table = create_backtest_metrics_table([Result()])

        self.assertIn("Legacy Aggregate Window Return %", table)
        self.assertIn("Legacy Mean Window CAGR %", table)
        self.assertIn("Legacy Max DD % (Uncorrected)", table)
        self.assertNotIn("Capital-Weighted Window Return %", table)

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


class TestShowBacktestRunsFromIndex(unittest.TestCase):
    def setUp(self):
        self.window = BacktestWindow(
            name="inspection",
            train_range=BacktestDateRange(
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2020, 6, 30, tzinfo=timezone.utc),
            ),
        )
        self.run = BacktestRun(
            backtest_window=self.window,
            number_of_orders=7,
            backtest_metrics=BacktestMetrics(
                backtest_window=self.window,
                cagr=0.1853, sharpe_ratio=0.54, total_net_gain=1800,
                initial_unallocated=10000, final_value=11800,
                number_of_trades=4, number_of_trades_closed=3,
                number_of_trades_open_at_end=1,
            ),
        )
        self.backtest = Backtest(
            algorithm_id="index-strategy",
            event_runs=[self.run], study_name="inspection-study",
        )
        self.index = BacktestIndex("/unused", pd.DataFrame({
            "bundle_path": ["one.obtf", "one.obtf"],
        }))
        self.options = {
            "study": "inspection-study",
            "run": self.window,
            "engine": "event",
            "columns": [
                ("cagr", "CAGR", ".2%"),
                ("sharpe_ratio", "Sharpe", ".2f"),
                ("total_net_gain", "Net gain (EUR)", ",.2f"),
            ],
        }

    def test_index_renders_same_metrics_as_existing_list_api(self):
        expected = show_backtest_runs([self.backtest], **self.options)
        with patch.object(
            BacktestIndex, "load_backtests", return_value=[self.backtest],
        ) as load:
            actual = show_backtest_runs(
                backtest_index=self.index, workers=1, **self.options,
            )
        load.assert_called_once_with(workers=1)
        self.assertEqual(actual, expected)
        self.assertIn("18.53%", actual)
        self.assertIn("0.54", actual)
        self.assertIn("1,800.00", actual)
        self.assertIn("index-strategy", actual)

    def test_run_columns_include_activity_counts_and_initial_balance(self):
        options = {
            **self.options,
            "columns": [
                ("initial_unallocated", "Initial balance", ",.2f"),
                ("final_value", "Final balance", ",.2f"),
                ("number_of_trades", "Trades", "d"),
                ("number_of_trades_closed", "Closed", "d"),
                ("number_of_trades_open_at_end", "Open at end", "d"),
                ("number_of_orders", "Orders", "d"),
            ],
        }
        with patch.object(
            BacktestIndex, "load_backtests", return_value=[self.backtest],
        ):
            rendered = show_backtest_runs(
                backtest_index=self.index, workers=1, **options,
            )
        values = [
            cell.strip() for cell in rendered.splitlines()[-1].split("|")
            if cell.strip()
        ]
        self.assertEqual(values, [
            "index-strategy", "event", "inspection",
            "10,000.00", "11,800.00", "4", "3", "1", "7",
        ])

    def test_sorting_uses_run_fields_when_not_present_on_metrics(self):
        second = Backtest(
            algorithm_id="fewer-orders",
            event_runs=[BacktestRun(
                backtest_window=self.window,
                backtest_metrics=BacktestMetrics(backtest_window=self.window),
                number_of_orders=2,
            )],
            study_name="inspection-study",
        )
        rendered = create_backtest_metrics_table(
            [second, self.backtest],
            level="run", engine="event", study="inspection-study",
            metrics=[("number_of_orders", "Orders", "d")],
            sort_by="number_of_orders", row_limit=1,
        )
        self.assertIn("index-strategy", rendered)
        self.assertNotIn("fewer-orders", rendered)

    def test_order_counts_are_scoped_to_each_window_including_zero(self):
        second_window = BacktestWindow(
            name="no-orders", train_range=self.window.train_range,
        )
        backtest = Backtest(
            algorithm_id="two-windows",
            event_runs=[
                self.run,
                BacktestRun(
                    backtest_window=second_window,
                    backtest_metrics=BacktestMetrics(
                        backtest_window=second_window,
                    ),
                    number_of_orders=0,
                ),
            ],
            study_name="inspection-study",
        )
        rendered = show_backtest_runs(
            backtests=[backtest], engine="event", study="inspection-study",
            columns=[("number_of_orders", "Orders", "d")],
        )
        rows = [
            [cell.strip() for cell in line.split("|") if cell.strip()]
            for line in [
                line for line in rendered.splitlines() if line.startswith("|")
            ][2:]
        ]
        self.assertEqual(
            [(row[2], row[3]) for row in rows],
            [("inspection", "7"), ("no-orders", "0")],
        )

    def test_legacy_templates_keep_percentage_point_scaling(self):
        rendered = show_backtest_runs(
            [self.backtest], study="inspection-study", engine="event",
            columns=[
                ("cagr", "CAGR %", "{:.2f}"),
                ("sharpe_ratio", "Sharpe", "{:.2f}"),
                ("total_net_gain", "Net gain", "{:,.2f}"),
            ],
        )
        self.assertIn("18.53", rendered)
        self.assertIn("0.54", rendered)
        self.assertIn("1,800.00", rendered)

    def test_bare_format_specs_use_raw_ratios_without_double_scaling(self):
        rendered = show_backtest_runs(
            [self.backtest], study="inspection-study", engine="event",
            columns=[
                ("cagr", "Annual return", ".2%"),
                ("cagr", "Raw ratio", ".4f"),
            ],
        )
        self.assertIn("18.53%", rendered)
        self.assertIn("0.1853", rendered)
        self.assertNotIn("1853.00%", rendered)

    def test_invalid_bare_format_spec_raises(self):
        with self.assertRaises(ValueError):
            show_backtest_runs(
                [self.backtest], study="inspection-study", engine="event",
                columns=[("cagr", "CAGR", ".not-a-format")],
            )

    def test_missing_metric_with_bare_format_is_na(self):
        rendered = show_backtest_runs(
            [self.backtest], study="inspection-study", engine="event",
            columns=[("missing_metric", "Unavailable", ".2f")],
        )
        self.assertIn("N/A", rendered)

    def test_worker_selection_is_forwarded_and_bundles_load_only_once(self):
        for workers in (None, 1, 2):
            with self.subTest(workers=workers), patch.object(
                BacktestIndex, "load_backtests", return_value=[self.backtest],
            ) as load:
                show_backtest_runs(
                    backtest_index=self.index, workers=workers, **self.options,
                )
                load.assert_called_once_with(workers=workers)

    def test_index_keeps_pagination_sorting_and_window_filtering(self):
        second = Backtest(
            algorithm_id="second",
            event_runs=[BacktestRun(
                backtest_window=self.window,
                backtest_metrics=BacktestMetrics(
                    backtest_window=self.window, cagr=0.5,
                ),
            )],
            study_name="inspection-study",
        )
        index = BacktestIndex("/unused", pd.DataFrame({
            "bundle_path": ["one.obtf", "two.obtf"],
        }))
        with patch.object(
            BacktestIndex, "load_backtests",
            return_value=[self.backtest, second],
        ):
            rendered = show_backtest_runs(
                backtest_index=index, workers=1, page=2, page_size=1,
                sort_by="cagr", **self.options,
            )
        self.assertIn("Page:** 2 of 2 (2 runs; 1 per page)", rendered)
        self.assertIn("index-strategy", rendered)
        self.assertNotIn("| second ", rendered)

    def test_empty_index_displays_no_data_without_loading(self):
        with patch.object(BacktestIndex, "load_backtests") as load:
            rendered = show_backtest_runs(
                backtest_index=BacktestIndex("/unused", pd.DataFrame()),
                workers=1,
            )
        load.assert_not_called()
        self.assertIn("No Data Available", rendered)
        self.assertIn("0 runs", rendered)

    def test_conflicting_or_missing_sources_raise_before_loading(self):
        with patch.object(BacktestIndex, "load_backtests") as load:
            for kwargs in (
                {},
                {"backtests": [], "backtest_index": self.index},
                {"backtests": [], "workers": 1},
            ):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        show_backtest_runs(**kwargs)
        load.assert_not_called()

    def test_invalid_index_type_raises_explicit_error(self):
        with self.assertRaisesRegex(TypeError, "must be a BacktestIndex"):
            show_backtest_runs(backtest_index=[])

    def test_invalid_index_paths_raise_before_loading(self):
        for frame in (
            pd.DataFrame({"algorithm_id": ["one"]}),
            pd.DataFrame({"bundle_path": [None]}),
            pd.DataFrame({"bundle_path": [""]}),
        ):
            with self.subTest(frame=frame), patch.object(
                BacktestIndex, "load_backtests",
            ) as load:
                with self.assertRaisesRegex(
                    OperationalException, "bundle_path",
                ):
                    show_backtest_runs(
                        backtest_index=BacktestIndex("/unused", frame),
                        workers=1,
                    )
                load.assert_not_called()

    def test_partial_bundle_load_cannot_render_successful_table(self):
        with patch.object(
            BacktestIndex, "load_backtests", return_value=[],
        ), patch(
            "investing_algorithm_framework.analysis.markdown."
            "create_backtest_metrics_table",
        ) as render:
            with self.assertRaisesRegex(OperationalException, "No partial"):
                show_backtest_runs(
                    backtest_index=self.index, workers=1, **self.options,
                )
        render.assert_not_called()

    def test_missing_bundle_raises_instead_of_showing_no_data(self):
        with TemporaryDirectory() as directory:
            index = BacktestIndex(directory, self.index.df.copy())
            with self.assertLogs(
                "investing_algorithm_framework", level="ERROR",
            ), self.assertRaisesRegex(OperationalException, "No partial"):
                show_backtest_runs(
                    backtest_index=index, workers=1, **self.options,
                )

    def test_real_loader_deduplicates_index_rows(self):
        with patch(
            "investing_algorithm_framework.domain.backtesting."
            "backtest_utils._load_one_bundle",
            return_value=self.backtest,
        ) as load:
            rendered = show_backtest_runs(
                backtest_index=self.index, workers=1, **self.options,
            )
        load.assert_called_once_with(str(Path("/unused") / "one.obtf"))
        self.assertIn("1 runs", rendered)

    def test_persisted_bundle_renders_through_index(self):
        with TemporaryDirectory() as directory:
            self.backtest.save(Path(directory) / "one.obtf")
            index = BacktestIndex(directory, self.index.df.copy())
            rendered = show_backtest_runs(
                backtest_index=index, workers=1,
                **{
                    **self.options,
                    "columns": [
                        *self.options["columns"],
                        ("number_of_orders", "Orders", "d"),
                        ("initial_unallocated", "Initial balance", ",.2f"),
                    ],
                },
            )
        self.assertIn("18.53%", rendered)
        self.assertIn("0.54", rendered)
        self.assertIn("1,800.00", rendered)
        self.assertIn("Orders", rendered)
        self.assertIn("10,000.00", rendered)
        self.assertIn("| 7 ", rendered)


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
