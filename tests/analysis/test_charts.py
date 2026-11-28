import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import numpy as np
import pandas as pd

from investing_algorithm_framework import (
    Backtest, BacktestDateRange, BacktestIndex, BacktestMetrics, BacktestRun,
    BacktestRunConfiguration, BacktestWindow, CCXTOHLCVDataProvider,
    CSVOHLCVDataProvider, DownloadResult, SignalSide,
    create_layered_equity_chart,
)
from investing_algorithm_framework.domain import PortfolioSnapshot


START = datetime(2025, 1, 1, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
RANGE = BacktestDateRange(START, START + 2 * HOUR)


def make_run(equity, *, window=None, snapshots=()):
    window = window or BacktestWindow(RANGE, name="window")
    return BacktestRun(
        backtest_window=window,
        backtest_metrics=BacktestMetrics(
            backtest_window=window, equity_curve=equity,
        ),
        portfolio_snapshots=snapshots,
    )


def make_candles(dates):
    bars = np.arange(len(dates))
    noise = np.cumsum(
        np.random.default_rng(42).normal(0, 0.005, len(dates)),
    )
    close = 100 * np.exp(
        0.0002 * bars + 0.03 * np.sin(bars / 20) + noise
    )
    previous = np.concatenate(([close[0]], close[:-1]))
    return pd.DataFrame({
        "Open": previous,
        "High": np.maximum(previous, close) * 1.003,
        "Low": np.minimum(previous, close) * 0.997,
        "Close": close,
        "Volume": 1000.0,
    }, index=dates)


class TestLayeredEquityChart(TestCase):
    def test_benchmark_preserves_equity_timestamps_and_uses_past_quotes(self):
        first = make_run([
            (1000, START), (1100, START + HOUR), (1000, START + 2 * HOUR),
        ])
        second = make_run([(2000, START), (1800, START + 2 * HOUR)])
        benchmark = pd.Series([50, 100, 150, 200], index=pd.DatetimeIndex([
            START - HOUR, START + HOUR / 2,
            START + 1.5 * HOUR, START + 3 * HOUR,
        ]))
        original = benchmark.copy()
        chart = create_layered_equity_chart([
            Backtest("first", vector_runs=[first]),
            Backtest("second", event_runs=[second]),
        ], RANGE, benchmark=benchmark, benchmark_label="S&P 500 (^GSPC)")
        spec = chart.to_dict()
        self.assertEqual(spec["data"]["columns"], {
            "equity_0": [1, 1.1, 1],
            "equity_1": [1, None, 0.9],
            "benchmark": [1, 2, 3],
        })
        self.assertEqual(
            spec["data"]["bars"]["time"],
            [int((START + i * HOUR).timestamp() * 1000) for i in range(3)],
        )
        panel = spec["panels"][0]
        self.assertEqual(panel["overlays"][-1]["label"], "S&P 500 (^GSPC)")
        self.assertGreater(panel["indicator"]["yRange"][1], 3)
        pd.testing.assert_series_equal(benchmark, original)

    def test_benchmark_does_not_backfill_before_its_first_quote(self):
        run = make_run([
            (100, START), (105, START + HOUR), (110, START + 2 * HOUR),
        ])
        benchmark = pd.Series(
            [100, 110],
            index=pd.DatetimeIndex([START + HOUR, START + 2 * HOUR]),
        )
        spec = create_layered_equity_chart(
            Backtest("strategy", vector_runs=[run]), RANGE,
            benchmark=benchmark,
        ).to_dict()
        self.assertEqual(
            spec["data"]["columns"]["benchmark"], [None, 1, 1.1],
        )

    def test_benchmark_carries_last_close_over_weekend(self):
        friday = pd.Timestamp("2025-01-03T21:00:00Z")
        monday = pd.Timestamp("2025-01-06T21:00:00Z")
        dates = [
            friday, friday + timedelta(days=1), friday + timedelta(days=2),
            monday - HOUR, monday, monday + HOUR,
        ]
        daterange = BacktestDateRange(friday, monday + HOUR)
        run = make_run(
            [(1000, date) for date in dates],
            window=BacktestWindow(daterange),
        )
        spec = create_layered_equity_chart(
            Backtest("strategy", event_runs=[run]), daterange,
            benchmark=pd.Series([100, 110], index=pd.DatetimeIndex([
                friday, monday,
            ])),
        ).to_dict()
        self.assertEqual(
            spec["data"]["columns"]["benchmark"], [1, 1, 1, 1, 1.1, 1.1],
        )

    def test_invalid_or_unavailable_benchmark_raises(self):
        backtest = Backtest("strategy", vector_runs=[
            make_run([(100, START)]),
        ])
        for benchmark, message in (
            (pd.Series([], index=pd.DatetimeIndex([])),
             "no equity observations"),
            (pd.Series([0], index=pd.DatetimeIndex([START])),
             "must be positive"),
            (pd.Series([float("inf")], index=pd.DatetimeIndex([START])),
             "finite"),
            (pd.Series([100], index=pd.DatetimeIndex([START + HOUR])),
             "no quotes available"),
            (pd.Series([100, 110], index=pd.DatetimeIndex([
                START - HOUR, START - HOUR,
            ])), "duplicate equity"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    create_layered_equity_chart(
                        backtest, RANGE, benchmark=benchmark,
                    )
        with self.assertRaisesRegex(ValueError, "normalize=True"):
            create_layered_equity_chart(
                backtest, RANGE, normalize=False,
                benchmark=pd.Series([100], index=pd.DatetimeIndex([START])),
            )
        with self.assertRaisesRegex(TypeError, "pandas Series"):
            create_layered_equity_chart(backtest, RANGE, benchmark=[])
        with self.assertRaisesRegex(TypeError, "DatetimeIndex"):
            create_layered_equity_chart(
                backtest, RANGE, benchmark=pd.Series([100]),
            )

    def test_sp500_loader_uses_download_v2_and_session_time_across_dst(self):
        from examples.charts import layered_equity_chart as example

        history = pd.DataFrame(
            {"Close": [100.0, 110.0], "Adj Close": [95.0, 100.0]},
            index=pd.DatetimeIndex([
                "2025-03-07", "2025-03-10",
            ]).tz_localize("America/New_York"),
        )
        daterange = BacktestDateRange("2025-03-07", "2025-03-11")
        with patch.object(
            example, "download_v2", return_value=DownloadResult(data=history),
        ) as download:
            prices = example.load_sp500_prices(daterange)
        pd.testing.assert_series_equal(prices, pd.Series(
            [100.0, 110.0], name="S&P 500 (^GSPC)",
            index=pd.to_datetime([
                "2025-03-07T21:00:00Z", "2025-03-10T20:00:00Z",
            ]),
        ))
        download.assert_called_once_with(
            symbol="^GSPC", market="YAHOO", time_frame="1d",
            start_date=datetime(2025, 2, 28, tzinfo=timezone.utc),
            end_date=datetime(2025, 3, 11, tzinfo=timezone.utc),
            warmup_window=0, pandas=True, save=False,
        )

    def test_sp500_loader_propagates_download_errors_and_empty_history(self):
        from examples.charts import layered_equity_chart as example

        with patch.object(
            example, "download_v2", side_effect=ImportError("Yahoo extra"),
        ):
            with self.assertRaisesRegex(ImportError, "Yahoo extra"):
                example.load_sp500_prices(RANGE)
        with patch.object(
            example, "download_v2",
            return_value=DownloadResult(data=pd.DataFrame()),
        ):
            with self.assertRaisesRegex(ValueError, "no S&P 500"):
                example.load_sp500_prices(RANGE)
        with patch.object(example, "load_sp500_prices") as load, patch.object(
            example, "generate_backtests",
        ) as generate:
            with self.assertRaisesRegex(ValueError, "normalize=True"):
                example.main(normalize=False, sp500=True)
            load.assert_not_called()
            generate.assert_not_called()

    def test_absolute_curves_preserve_currency_values_and_gaps(self):
        first = make_run([
            (1000, START - HOUR), (2000, START), (3000, START + 2 * HOUR),
        ])
        second = make_run([
            (500, START + HOUR), (400, START + 2 * HOUR),
        ])
        original = list(first.backtest_metrics.equity_curve)
        chart = create_layered_equity_chart([
            Backtest("first", vector_runs=[first]),
            Backtest("second", event_runs=[second]),
        ], RANGE, normalize=False)
        spec = json.loads(chart.to_json())
        self.assertEqual(spec["data"]["columns"], {
            "equity_0": [2000, None, 3000],
            "equity_1": [None, 500, 400],
        })
        panel = spec["panels"][0]
        self.assertEqual(panel["title"], "Absolute Equity")
        self.assertNotIn("refLines", panel["indicator"])
        lower, upper = panel["indicator"]["yRange"]
        self.assertLess(lower, 400)
        self.assertGreater(upper, 3000)
        self.assertEqual(list(first.backtest_metrics.equity_curve), original)

    def test_absolute_mode_accepts_nonpositive_starts_and_flat_curves(self):
        for values in ([0, 0], [-100, -50], [10_000, 10_000]):
            with self.subTest(values=values):
                run = make_run([
                    (values[0], START), (values[1], START + HOUR),
                ])
                spec = create_layered_equity_chart(
                    Backtest("absolute", event_runs=[run]), RANGE,
                    normalize=False,
                ).to_dict()
                self.assertEqual(
                    spec["data"]["columns"]["equity_0"], values,
                )
                lower, upper = spec["panels"][0]["indicator"]["yRange"]
                self.assertLess(lower, min(values))
                self.assertGreater(upper, max(values))

    def test_absolute_mode_rejects_nonfinite_values_and_ranges(self):
        for value, message in (
            (float("inf"), "equity must be finite"),
            (float("nan"), "equity must be finite"),
            (np.finfo(float).max, "Equity range is too large"),
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, message):
                    create_layered_equity_chart(
                        Backtest("invalid", event_runs=[
                            make_run([(value, START)]),
                        ]), RANGE, normalize=False,
                    )

    def test_advanced_indicators_are_causal_and_signals_do_not_conflict(self):
        from examples.charts import layered_equity_chart as example

        candles = make_candles(pd.date_range(
            START, periods=300, freq="2h",
        ))
        original = candles.copy()
        strategy = example.TrendPullbackStrategy()
        full = strategy.calculate_indicators(candles)
        prefix = strategy.calculate_indicators(candles.iloc[:150])
        pd.testing.assert_frame_equal(candles, original)
        pd.testing.assert_frame_equal(full.iloc[:150], prefix)
        signals = {
            signal.side: signal.series for signal
            in strategy.generate_signal_series({"btc_2h": candles})
        }
        entries = signals[SignalSide.OPEN_LONG]
        exits = signals[SignalSide.CLOSE_LONG]
        self.assertTrue(entries.any())
        self.assertTrue(exits.any())
        self.assertFalse((entries & exits).any())

    def test_volatility_filter_blocks_entries_without_blocking_exits(self):
        from examples.charts import layered_equity_chart as example

        candles = make_candles(pd.date_range(
            START, periods=300, freq="2h",
        ))
        signals = {
            signal.side: signal.series for signal
            in example.TrendPullbackStrategy(
                max_atr_percentage=0.01,
            ).generate_signal_series({"btc_2h": candles})
        }
        self.assertFalse(signals[SignalSide.OPEN_LONG].any())
        self.assertTrue(signals[SignalSide.CLOSE_LONG].any())

    def test_example_window_name_uses_public_date_range_bounds(self):
        from examples.charts import layered_equity_chart as example

        with TemporaryDirectory() as directory:
            with patch.object(example, "create_app") as create_app:
                example.generate_backtests(Path(directory))
                study = create_app.return_value.run_backtest.call_args.kwargs[
                    "study"
                ]
        window = study.backtest_windows[0]
        self.assertEqual(window.train_range, example.DATE_RANGE)
        self.assertEqual(
            window.name,
            f"window_{example.DATE_RANGE.start_date}_"
            f"{example.DATE_RANGE.end_date}",
        )

    def test_identical_opening_snapshots_are_collapsed_without_mutation(self):
        run = make_run([
            (100, START), (100, START), (110, START + HOUR),
        ])
        original = list(run.backtest_metrics.equity_curve)
        spec = create_layered_equity_chart(
            Backtest("opening-snapshot", vector_runs=[run]), RANGE,
        ).to_dict()
        self.assertEqual(spec["data"]["columns"]["equity_0"], [1, 1.1])
        self.assertEqual(list(run.backtest_metrics.equity_curve), original)

    def test_example_runs_real_independent_backtests_without_network(self):
        from examples.charts import layered_equity_chart as example

        with TemporaryDirectory() as directory:
            candles = make_candles(pd.date_range(
                example.DATE_RANGE.start_date - 100 * example.BAR,
                example.DATE_RANGE.end_date, freq="2h",
            ))
            csv_path = Path(directory) / "candles.csv"
            candles.rename_axis("Datetime").reset_index().to_csv(
                csv_path, index=False,
            )
            provider = CSVOHLCVDataProvider(
                storage_path=str(csv_path), symbol="BTC/EUR",
                market="BITVAVO", time_frame="2h", warmup_window=50,
            )

            def quiet_configuration(**kwargs):
                kwargs["show_progress"] = False
                return BacktestRunConfiguration(**kwargs)

            with patch.object(
                socket.socket, "connect",
                side_effect=AssertionError("Unexpected network access"),
            ) as connect, patch.object(
                CCXTOHLCVDataProvider, "has_data", return_value=False,
            ), patch.object(
                example, "BacktestRunConfiguration",
                side_effect=quiet_configuration,
            ):
                index = example.generate_backtests(
                    Path(directory), data_provider=provider,
                )
                backtests = list(index.iter_backtests())
                chart = create_layered_equity_chart(index, example.DATE_RANGE)
                connect.assert_not_called()

            self.assertEqual(len(backtests), 3)
            trade_counts = {}
            for backtest in backtests:
                with self.subTest(algorithm_id=backtest.algorithm_id):
                    runs = backtest.get_runs(
                        "event", study="Sample Backtest",
                    )
                    self.assertEqual(len(runs), 1)
                    trade_counts[backtest.algorithm_id] = len(
                        runs[0].get_trades(),
                    )
            baseline_count = trade_counts.pop("EMA10-RSI21-TP12-SL6")
            for count in trade_counts.values():
                self.assertGreater(count, baseline_count)

            spec = json.loads(chart.to_json())
            self.assertEqual(len(spec["panels"]), 1)
            self.assertEqual(len(spec["panels"][0]["overlays"]), 2)
            changing_curves = 0
            for values in spec["data"]["columns"].values():
                self.assertEqual(values[0], 1)
                changing_curves += any(value != 1 for value in values)
            self.assertGreaterEqual(changing_curves, 2)

            with patch.object(
                example, "generate_backtests", return_value=index,
            ) as generate, patch.object(
                example.webbrowser, "open", return_value=True,
            ) as opened, patch("finterion_charts.ChartSpec.show") as hosted:
                example.main()
                generate.assert_called_once_with()
                chart_path = index.directory / "layered_equity_chart.html"
                opened.assert_called_once_with(chart_path.as_uri())
                hosted.assert_not_called()
                html = chart_path.read_text(encoding="utf-8")
                self.assertIn('<meta charset="utf-8">', html)
                self.assertIn("<iframe srcdoc=", html)
                self.assertNotIn(
                    'src="https://charts.finterion.com', html,
                )
            with patch.object(
                example, "generate_backtests", return_value=index,
            ), patch.object(
                example.webbrowser, "open", return_value=True,
            ), patch.object(
                example, "create_layered_equity_chart",
                wraps=create_layered_equity_chart,
            ) as build_chart:
                example.main(normalize=False)
                build_chart.assert_called_once_with(
                    index, example.DATE_RANGE, normalize=False,
                    benchmark=None, benchmark_label="S&P 500 (^GSPC)",
                )
                self.assertIn(
                    "Absolute Equity", chart_path.read_text(encoding="utf-8"),
                )
            benchmark = pd.Series(
                [5000, 5500], index=pd.DatetimeIndex([
                    example.DATE_RANGE.start_date, example.DATE_RANGE.end_date,
                ]),
            )
            with patch.object(
                example, "generate_backtests", return_value=index,
            ), patch.object(
                example, "load_sp500_prices", return_value=benchmark,
            ) as load, patch.object(
                example.webbrowser, "open", return_value=True,
            ), patch.object(
                example, "create_layered_equity_chart",
                wraps=create_layered_equity_chart,
            ) as build_chart:
                example.main(sp500=True)
                load.assert_called_once_with(example.DATE_RANGE)
                build_chart.assert_called_once_with(
                    index, example.DATE_RANGE, normalize=True,
                    benchmark=benchmark, benchmark_label="S&P 500 (^GSPC)",
                )
            with patch.object(
                example, "generate_backtests", return_value=index,
            ), patch.object(example.webbrowser, "open", return_value=False):
                with self.assertRaisesRegex(
                    RuntimeError, "Could not open a browser",
                ):
                    example.main()

    def test_curves_are_clipped_sorted_normalized_and_aligned_with_gaps(self):
        first = make_run([
            (300, START + 2 * HOUR), (100, START - HOUR), (200, START),
        ])
        second = make_run([
            (50, START + HOUR), (-25, START + 2 * HOUR),
        ])
        original = list(first.backtest_metrics.equity_curve)
        chart = create_layered_equity_chart([
            Backtest("first", vector_runs=[first]),
            Backtest("second", event_runs=[second]),
        ], RANGE)
        spec = json.loads(chart.to_json())
        self.assertEqual(len(spec["panels"]), 1)
        self.assertEqual(
            spec["data"]["columns"],
            {"equity_0": [1, None, 1.5], "equity_1": [None, 1, -0.5]},
        )
        self.assertEqual(
            spec["data"]["bars"]["time"],
            [int((START + i * HOUR).timestamp() * 1000) for i in range(3)],
        )
        panel = spec["panels"][0]
        lower, upper = panel["indicator"]["yRange"]
        self.assertLess(lower, -0.5)
        self.assertGreater(upper, 1.5)
        self.assertIn("first / default / vector", panel["indicator"]["label"])
        self.assertIn(
            "second / default / event", panel["overlays"][0]["label"],
        )
        self.assertNotEqual(
            panel["indicator"]["color"], panel["overlays"][0]["color"],
        )
        self.assertEqual(list(first.backtest_metrics.equity_curve), original)

    def test_single_backtest_includes_both_engines_and_all_studies(self):
        backtest = Backtest(
            "algorithm", study_name="first",
            vector_runs=[make_run([(100, START), (110, START + HOUR)])],
            event_runs=[make_run([(100, START), (105, START + HOUR)])],
        )
        second = Backtest(
            "algorithm", study_name="second",
            event_runs=[make_run([(200, START), (180, START + HOUR)])],
        )
        backtest.add_study(second.get_study("second"))
        panel = create_layered_equity_chart(backtest, RANGE).to_dict()[
            "panels"
        ][0]
        self.assertEqual(len(panel["overlays"]), 2)
        labels = [panel["indicator"]["label"]] + [
            overlay["label"] for overlay in panel["overlays"]
        ]
        self.assertTrue(any("first / vector" in label for label in labels))
        self.assertTrue(any("first / event" in label for label in labels))
        self.assertTrue(any("second / event" in label for label in labels))

    def test_index_loads_persisted_bundle_once_and_snapshot_fallback(self):
        run = make_run([], snapshots=[
            PortfolioSnapshot(total_value=value, created_at=START + i * HOUR)
            for i, value in enumerate((100, 125, 150))
        ])
        backtest = Backtest("persisted", event_runs=[run])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "backtest.obtf"
            backtest.save_bundle(path)
            index = BacktestIndex(directory, pd.DataFrame({
                "bundle_path": ["backtest.obtf", "backtest.obtf"],
            }))
            with patch.object(
                Backtest, "open", wraps=Backtest.open,
            ) as opened:
                spec = create_layered_equity_chart(index, RANGE).to_dict()
            self.assertEqual(opened.call_count, 1)
        self.assertEqual(spec["data"]["columns"], {
            "equity_0": [1, 1.25, 1.5],
        })
        self.assertNotIn("overlays", spec["panels"][0])

    def test_empty_nonoverlapping_and_invalid_selected_equity_raise(self):
        cases = [
            ([], "No backtest runs overlap"),
            ([make_run([])], "no equity observations"),
            ([make_run([(0, START)])], "initial selected equity"),
            ([make_run([(-1, START)])], "initial selected equity"),
            ([make_run([(float("inf"), START)])], "equity must be finite"),
            ([make_run([(100, START), (110, START)])], "duplicate equity"),
            ([make_run([
                (100, START), (100, START + timedelta(microseconds=1)),
            ])], "duplicate equity"),
            ([make_run([(100, None)])], "invalid equity timestamp"),
            ([make_run([(100, START - HOUR)])], "no equity observations"),
        ]
        for runs, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    create_layered_equity_chart(
                        Backtest("invalid", event_runs=runs), RANGE,
                    )
        unrelated = make_run([], window=BacktestWindow(BacktestDateRange(
            START + 3 * HOUR, START + 4 * HOUR,
        )))
        valid = make_run([(100, START), (110, START + HOUR)])
        spec = create_layered_equity_chart(
            Backtest("selected", event_runs=[unrelated, valid]), RANGE,
        ).to_dict()
        self.assertEqual(spec["data"]["columns"]["equity_0"], [1, 1.1])

    def test_invalid_input_types_raise(self):
        with self.assertRaisesRegex(TypeError, "normalize"):
            create_layered_equity_chart([], RANGE, normalize="false")
        with self.assertRaisesRegex(TypeError, "BacktestDateRange"):
            create_layered_equity_chart([], (START, START + HOUR))
        with self.assertRaisesRegex(TypeError, "Backtest objects"):
            create_layered_equity_chart([object()], RANGE)
