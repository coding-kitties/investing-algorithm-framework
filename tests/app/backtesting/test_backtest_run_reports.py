from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange, BacktestEngine, BacktestIndex, BacktestRunConfiguration,
    BacktestWindow, CSVOHLCVDataProvider, DecisionTrace, DecisionTraceEntry,
    RESOURCE_DIRECTORY, Study, Universe, create_app, IndicatorConfig,
    StopLossRule, TakeProfitRule, SignalSide,
)
from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_session_index import SESSION_INDEX_FILENAME
from investing_algorithm_framework.services.run_reports import RunReportService
from investing_algorithm_framework.services.backtest_store.recording import \
    iter_signal_reports
from tests.scenarios.vector_vs_event_backtests.test_event_vs_vector_backtest \
    import CSV_FILENAME, LONG_START_DATE, LONG_END_DATE, SHORT_START_DATE, \
    SHORT_END_DATE, LongCycleStrategy, WARMUP


class ReportedLongCycleStrategy(LongCycleStrategy):
    def generate_signals(self, context, data):
        trace = DecisionTrace.of(
            DecisionTraceEntry(
                "close", float(data["BTC_EUR_OHLCV"]["Close"].iloc[-1]),
                group="indicators",
            ),
            summary="Observed close",
        )
        signals = list(super().generate_signals(context, data))
        if not signals:
            self.record_decision_trace(trace, symbol="BTC")
        for signal in signals:
            yield signal.with_decision_trace(trace)


class FailingReportStrategy(ReportedLongCycleStrategy):
    def generate_signals(self, context, data):
        if data["BTC_EUR_OHLCV"]["Close"].iloc[-1] == 100:
            raise RuntimeError("Historical tick failed")
        yield from super().generate_signals(context, data)


class ProtectiveReportStrategy(ReportedLongCycleStrategy):
    def generate_signals(self, context, data):
        for signal in super().generate_signals(context, data):
            if signal.side is SignalSide.OPEN_LONG:
                yield signal


class TestBacktestRunReports(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.addCleanup(teardown_sqlalchemy)
        self.app = create_app(
            name=f"run-reports-{uuid4().hex}",
            config={RESOURCE_DIRECTORY: self.storage.name},
        )
        csv_path = (
            Path(__file__).parents[2] / "resources" / "test_data" / "ohlcv"
            / CSV_FILENAME
        )
        self.app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv_path), symbol="BTC/EUR", time_frame="2h",
            market="BITVAVO", warmup_window=WARMUP,
        ))
        self.study = Study(
            name="run-report-test",
            universe=Universe(
                market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
            ),
            initial_capital=1000,
            engines=[BacktestEngine.EVENT_DRIVEN],
            backtest_windows=[BacktestWindow(train_range=BacktestDateRange(
                name="long", start_date=LONG_START_DATE,
                end_date=LONG_END_DATE,
            ))],
        )
        self.configuration = BacktestRunConfiguration(
            capture_run_reports=True, show_progress=False,
            continue_on_error=False,
            backtest_storage_directory=Path(self.storage.name) / "backtests",
        )
        self.strategy = ReportedLongCycleStrategy(algorithm_id="reported")

    def run_backtest(self, **kwargs):
        return self.app.run_backtest(
            study=self.study,
            run_configuration=kwargs.pop(
                "run_configuration", self.configuration,
            ),
            **({"strategy": self.strategy} if not kwargs else kwargs),
        )

    def test_default_reports_are_none(self):
        from investing_algorithm_framework import IndicatorEngine

        self.strategy.indicator_configs = [IndicatorConfig(
            id="trend", indicator="ema", period=1,
            data_source="BTC_EUR_OHLCV",
        )]
        with patch.object(
            IndicatorEngine, "snapshot",
            side_effect=AssertionError("Disabled capture must not snapshot"),
        ) as snapshot:
            index = self.run_backtest(run_configuration=replace(
                self.configuration, capture_run_reports=False,
            ))
        snapshot.assert_not_called()
        self.assertIsNone(index.run_reports)

    def test_stop_loss_trigger_and_later_fill_are_captured_without_signals(self):
        self.strategy = ProtectiveReportStrategy(algorithm_id="reported")
        self.strategy.stop_losses = [StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100,
        )]
        index = self.run_backtest(run_configuration=replace(
            self.configuration, persist_run_reports=True,
        ))
        self._assert_protective_reports(index, "stop_losses", 100)
        reopened = BacktestIndex.open(
            index.directory, filename=SESSION_INDEX_FILENAME,
        )
        self.assertEqual(index.run_reports, reopened.load_run_reports())

    def test_take_profit_trigger_and_later_fill_are_captured_without_signals(self):
        self.strategy = ProtectiveReportStrategy(algorithm_id="reported")
        self.strategy.take_profits = [TakeProfitRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100,
        )]
        self.study = replace(self.study, backtest_windows=[
            BacktestWindow(train_range=BacktestDateRange(
                name="profit", start_date=LONG_START_DATE,
                end_date=SHORT_END_DATE,
            )),
        ])
        self._assert_protective_reports(
            self.run_backtest(), "take_profits", 120,
        )

    def _assert_protective_reports(self, index, key, trigger_price):
        reports = [report for report in index.run_reports if report[key]]
        self.assertTrue(reports)
        self.assertEqual([], reports[0]["signals"])
        trigger = reports[0][key][0]
        self.assertEqual("trigger", trigger["event_type"])
        self.assertEqual(trigger_price, trigger["price"])
        self.assertTrue(trigger["rules"])
        self.assertTrue(trigger["trades"])
        self.assertEqual("ProtectiveReportStrategy", trigger["strategy_id"])
        fills = [e for report in reports for e in report[key] if e["event_type"] == "fill"]
        self.assertTrue(fills)
        self.assertGreater(fills[0]["timestamp"], trigger["timestamp"])
        self.assertEqual(trigger_price, fills[0]["price"])
        self.assertEqual(trigger["order_id"], fills[0]["order_id"])

    def test_capture_actual_ticks_without_persisting_reports(self):
        with patch.object(
            RunReportService, "create",
            side_effect=AssertionError("Historical reports must be transient"),
        ) as persist:
            index = self.run_backtest()
        persist.assert_not_called()
        reports = index.run_reports
        self.assertEqual(len(reports), 5)
        timestamps = [
            datetime.fromisoformat(report["timestamp"]) for report in reports
        ]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(timestamps[0], LONG_START_DATE)
        self.assertEqual(timestamps[-1], LONG_END_DATE)
        self.assertTrue(all(
            isinstance(report["id"], str) and report["status"] == "completed"
            and report["started_at"] == report["completed_at"]
            and report["algorithm_id"] == "reported"
            and report["study_name"] == self.study.name
            and report["backtest_start_date"] == LONG_START_DATE.isoformat()
            for report in reports
        ))
        self.assertEqual(
            len(reports), len({report["id"] for report in reports}),
        )
        for report in reports:
            self.assertEqual(
                ["ReportedLongCycleStrategy"], report["strategy_ids"],
            )
            self.assertEqual("BACKTEST", report["environment"])
            self.assertNotIn("reason", report)
            self.assertNotIn("is_paper", report)
            self.assertEqual(1, len(report["indicators"]))
            self.assertEqual({
                "strategy_id": "ReportedLongCycleStrategy",
                "symbol": "BTC", "timestamp": report["timestamp"],
                "name": "close",
                "value": (
                    report["decision_traces"][0]["entries"][0]["value"]
                    if report["decision_traces"] else
                    report["signals"][0]["metadata"]
                    ["decision_trace"]["entries"][0]["value"]
                ),
            }, report["indicators"][0])
        self.assertTrue(any(
            not report["signals"]
            and report["decision_traces"][0]["entries"][0]["value"] == 100
            for report in reports
        ))
        signals = [
            signal for report in reports for signal in report["signals"]
        ]
        self.assertEqual(
            [signal["side"] for signal in signals],
            ["open_long", "close_long"],
        )
        self.assertTrue(all(
            signal["status"] == "approved" for signal in signals
        ))
        self.assertTrue(reports[0]["orders"])
        json.dumps(reports, allow_nan=False)
        self.assertNotEqual(
            reports[0]["orders"][0]["status"],
            reports[1]["orders"][0]["status"],
        )
        self.assertIsNot(reports[0]["positions"], reports[1]["positions"])
        signals[0]["metadata"]["decision_trace"]["entries"][0]["value"] = -999
        self.assertEqual(
            reports[1]["decision_traces"][0]["entries"][0]["value"], 100,
        )
        self.assertIsNone(BacktestIndex.open(
            index.directory, filename=SESSION_INDEX_FILENAME,
        ).run_reports)
        self.assertNotIn("run_reports", index.df.columns)
        self.assertFalse(hasattr(index.load_backtests()[0], "run_reports"))
        self.assertFalse((index.directory / "run_reports").exists())

    def test_persisted_reports_round_trip_without_implicit_loading(self):
        self.strategy.indicator_configs = [
            IndicatorConfig(
                id=name, indicator="ema", period=period,
                data_source="BTC_EUR_OHLCV",
            )
            for name, period in (("trend", 1), ("unused", 3))
        ]
        index = self.run_backtest(run_configuration=replace(
            self.configuration, persist_run_reports=True,
        ))
        references = index.df["run_reports_path"].drop_duplicates().tolist()
        self.assertEqual(len(references), 1)
        self.assertTrue(references[0].endswith(".jsonl.gz"))
        self.assertTrue((index.directory / references[0]).is_file())
        with patch(
            "investing_algorithm_framework.domain.backtesting."
            "run_report_storage.iter_run_reports",
            side_effect=AssertionError("Reports must load explicitly"),
        ):
            reopened = BacktestIndex.open(
                index.directory, filename=SESSION_INDEX_FILENAME,
            )
            self.assertIsNone(reopened.run_reports)
            for report in index.run_reports:
                self.assertEqual(
                    {"close", "trend.value", "unused.value"},
                    {item["name"] for item in report["indicators"]},
                )
                self.assertEqual(3, len(report["indicators"]))
            self.assertEqual(
                reopened.get_backtest("reported").algorithm_id, "reported",
            )
        self.assertEqual(reopened.load_run_reports(), index.run_reports)
        self.assertEqual(
            reopened.load_run_reports(algorithm_id="reported"),
            index.run_reports,
        )
        self.assertIsNone(reopened.run_reports)

    def test_persisted_reports_respect_algorithm_filters_and_windows(self):
        self.study.backtest_windows.append(BacktestWindow(
            train_range=BacktestDateRange(
                name="short", start_date=SHORT_START_DATE,
                end_date=SHORT_END_DATE,
            ),
        ))
        index = self.run_backtest(
            strategies=[
                self.strategy,
                ReportedLongCycleStrategy(algorithm_id="second"),
            ],
            run_configuration=replace(
                self.configuration, persist_run_reports=True,
            ),
        )
        reopened = BacktestIndex.open(
            index.directory, filename=SESSION_INDEX_FILENAME,
        )
        self.assertEqual(reopened.load_run_reports(), index.run_reports)
        expected = [
            report for report in index.run_reports
            if report["algorithm_id"] == "second"
        ]
        self.assertEqual(len(expected), 10)
        self.assertEqual(
            reopened.load_run_reports(algorithm_id="second"), expected,
        )
        self.assertEqual(
            reopened.filter(
                lambda row: row["algorithm_id"] == "second",
            ).load_run_reports(),
            expected,
        )
        self.assertEqual(
            reopened.filter(lambda row: False).load_run_reports(), [],
        )

    def test_repeated_sessions_keep_immutable_report_references(self):
        configuration = replace(
            self.configuration, persist_run_reports=True,
        )
        first = self.run_backtest(run_configuration=configuration)
        first.df.to_parquet(
            first.directory / "previous_session.parquet", index=False,
        )
        self.study.name = "second-session"
        second = self.run_backtest(run_configuration=configuration)
        self.assertNotEqual(
            first.df["run_reports_path"].iloc[0],
            second.df["run_reports_path"].iloc[0],
        )
        self.assertEqual(first.load_run_reports(), first.run_reports)
        self.assertEqual(second.load_run_reports(), second.run_reports)
        self.assertEqual(
            BacktestIndex.open(
                first.directory, filename="previous_session.parquet",
            ).load_run_reports(),
            first.run_reports,
        )
        self.assertEqual(
            BacktestIndex.open(
                second.directory, filename=SESSION_INDEX_FILENAME,
            ).load_run_reports(),
            second.run_reports,
        )

    def test_persisted_loading_respects_final_metrics_pruning(self):
        index = self.run_backtest(
            strategies=[
                self.strategy,
                ReportedLongCycleStrategy(algorithm_id="second"),
            ],
            run_configuration=replace(
                self.configuration, persist_run_reports=True,
            ),
            final_metrics_filter_function=lambda selected: selected.filter(
                lambda row: row["algorithm_id"] == "second",
            ),
        )
        self.assertEqual(len(index.run_reports), 10)
        self.assertEqual(index.get_algorithm_ids(), ["second"])
        self.assertEqual(index.load_run_reports(), [
            report for report in index.run_reports
            if report["algorithm_id"] == "second"
        ])

    def test_persistence_failure_propagates_even_when_continuing(self):
        with patch(
            "investing_algorithm_framework.domain.backtesting."
            "run_report_storage.save_run_reports",
            side_effect=OSError("Disk full"),
        ):
            with self.assertRaisesRegex(OSError, "Disk full"):
                self.run_backtest(run_configuration=replace(
                    self.configuration, persist_run_reports=True,
                    continue_on_error=True,
                ))

    def test_capture_replays_checkpoints(self):
        first = self.run_backtest()
        second = self.run_backtest()
        self.assertEqual(len(first.run_reports), len(second.run_reports))
        self.assertEqual(len(second.run_reports), 5)
        self.assertEqual(
            first.run_reports[0]["timestamp"],
            second.run_reports[0]["timestamp"],
        )

    def test_capture_multiple_algorithms_and_windows_and_filter(self):
        self.study.backtest_windows.append(BacktestWindow(
            train_range=BacktestDateRange(
                name="short", start_date=SHORT_START_DATE,
                end_date=SHORT_END_DATE,
            ),
        ))
        index = self.run_backtest(strategies=[
            self.strategy, ReportedLongCycleStrategy(algorithm_id="second"),
        ])
        self.assertEqual(len(index.run_reports), 20)
        self.assertEqual(
            {(report["algorithm_id"], report["backtest_start_date"])
             for report in index.run_reports},
            {(algorithm, start.isoformat())
             for algorithm in ("reported", "second")
             for start in (LONG_START_DATE, SHORT_START_DATE)},
        )
        filtered = index.filter(lambda row: row["algorithm_id"] == "second")
        self.assertEqual(len(filtered.run_reports), 10)
        self.assertEqual(
            {report["algorithm_id"] for report in filtered.run_reports},
            {"second"},
        )
        self.assertEqual(index.filter(lambda row: False).run_reports, [])

    def test_failure_report_is_returned_when_continuing(self):
        index = self.run_backtest(
            strategy=FailingReportStrategy(
                algorithm_id="failure",
                indicator_configs=[IndicatorConfig(
                    id="trend", indicator="ema", period=1,
                    data_source="BTC_EUR_OHLCV",
                )],
            ),
            run_configuration=replace(
                self.configuration, continue_on_error=True,
            ),
        )
        failed = index.run_reports[-1]
        self.assertEqual(failed["status"], "execution_error")
        self.assertEqual(failed["error"], "Historical tick failed")
        self.assertEqual(1, len(failed["indicators"]))
        self.assertEqual("trend.value", failed["indicators"][0]["name"])
        self.assertEqual(
            failed["timestamp"], failed["indicators"][0]["timestamp"],
        )
        self.assertNotIn("reason", failed)
        self.assertEqual(len(index.run_reports), 2)

    def test_reject_vector_capture(self):
        self.study.engines = [BacktestEngine.VECTOR]
        with self.assertRaisesRegex(OperationalException, "event-driven"):
            self.run_backtest()

    def test_reject_multi_engine_capture(self):
        self.study.engines = [
            BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR,
        ]
        with self.assertRaisesRegex(OperationalException, "single event"):
            self.run_backtest()

    def test_reject_optimization_capture(self):
        with self.assertRaisesRegex(OperationalException, "optimization"):
            self.run_backtest(strategy=self.strategy, optimization=Mock())

    def test_capture_preserves_streamed_signal_history(self):
        index = self.run_backtest(run_configuration=replace(
            self.configuration,
            signal_storage_directory=Path(self.storage.name) / "signals",
        ))
        self.assertEqual(len(index.run_reports), 5)
        backtest = index.load_backtests()[0]
        reference = backtest.event_runs[0].metadata["signal_history"]
        self.assertEqual(reference["count"], 5)
        recorded = list(iter_signal_reports(
            Path(self.storage.name) / "signals", reference,
        ))
        self.assertEqual(
            [signal for tick in recorded for signal in tick["signals"]],
            [{
                key: value for key, value in signal.items()
                if key not in ("strategy_id", "timestamp")
            } for report in index.run_reports for signal in report["signals"]],
        )

    def test_capture_memory_state_backend(self):
        index = self.run_backtest(run_configuration=replace(
            self.configuration, event_state_backend="memory",
        ))
        self.assertEqual(len(index.run_reports), 5)
        self.assertTrue(index.run_reports[-1]["portfolios"])

    def test_configuration_validation_and_environment(self):
        with self.assertRaisesRegex(ValueError, "must be a bool"):
            BacktestRunConfiguration(capture_run_reports=1)
        for workers in (-1, 1, 2):
            with self.subTest(workers=workers), self.assertRaisesRegex(
                ValueError, "sequential",
            ):
                BacktestRunConfiguration(
                    capture_run_reports=True, n_workers=workers,
                )
        self.assertTrue(BacktestRunConfiguration.from_env(environment={
            "IAF_BACKTEST_CAPTURE_RUN_REPORTS": "true",
        }).capture_run_reports)
        self.assertIsNone(BacktestIndex(
            self.storage.name, pd.DataFrame(columns=["algorithm_id"]),
        ).filter(lambda row: True).run_reports)
        self.assertFalse(BacktestRunConfiguration().persist_run_reports)
        with self.assertRaisesRegex(ValueError, "must be a bool"):
            BacktestRunConfiguration(persist_run_reports=1)
        with self.assertRaisesRegex(ValueError, "requires capture"):
            BacktestRunConfiguration(persist_run_reports=True)
        configuration = BacktestRunConfiguration.from_env(environment={
            "IAF_BACKTEST_CAPTURE_RUN_REPORTS": "true",
            "IAF_BACKTEST_PERSIST_RUN_REPORTS": "true",
        })
        self.assertTrue(configuration.persist_run_reports)
