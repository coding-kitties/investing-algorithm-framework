import os
import shutil
import json
from tempfile import TemporaryDirectory
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    MarketCredential, Schedule, PositionSize, Signal, SignalSide, \
    ScoreCard, ScoreCardEntry, DecisionTrace, DecisionTraceEntry, RunReport, \
    DataSource, IndicatorConfig, ConfluenceScoringStrategy, \
    ConfluenceScoreConfig, IndicatorRule
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from tests.resources import random_string, OrderExecutorTest, \
    PortfolioProviderTest
from investing_algorithm_framework.app.algorithm_runner import (
    AlgorithmRunner, RUNNING,
)
from investing_algorithm_framework.domain import OperationalException


class OpenLongOnceStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=50.0)
    ]

    def generate_signals(self, context, data):
        yield Signal(symbol="BTC", side=SignalSide.OPEN_LONG)


class ScoreCardStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=50.0)
    ]

    def generate_signals(self, context, data):
        card = ScoreCard.of(
            ScoreCardEntry("rsi_14", 28.4),
            ScoreCardEntry("close", 41500.0, unit="EUR"),
            summary="RSI oversold",
        )
        yield Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG
        ).with_score_card(card)


class NoSignalScoreCardStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]

    def generate_signals(self, context, data):
        card = ScoreCard.of(
            ScoreCardEntry("rsi_14", 55.0),
            summary="RSI neutral - no signal",
        )
        self.record_score_card(card, symbol="BTC")
        return
        yield


class OpenLongOnceEverStrategy(TradingStrategy):
    """Signals exactly once across the lifetime of the process, so a
    second ``app.run()`` call on the same app creates no new order —
    used to test that a pre-existing order gets picked up by a later
    run's report when it is *updated* (e.g. filled) rather than
    created during that run.
    """
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=50.0)
    ]
    _fired = False

    def generate_signals(self, context, data):
        if OpenLongOnceEverStrategy._fired:
            return
        OpenLongOnceEverStrategy._fired = True
        yield Signal(symbol="BTC", side=SignalSide.OPEN_LONG)


class NoSignalDecisionTraceStrategy(NoSignalScoreCardStrategy):
    def generate_signals(self, context, data):
        self.record_decision_trace(DecisionTrace.of(
            DecisionTraceEntry("rsi_14", 55.0), summary="No entry",
        ), symbol="BTC")
        return iter(())


class IndicatorSnapshotStrategy(NoSignalDecisionTraceStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    data_sources = [DataSource(
        identifier="indicator_prices", symbol="BTC/EUR", market="BINANCE",
        data_type="ohlcv", time_frame="2h", pandas=True,
    )]
    indicator_configs = [
        IndicatorConfig(
            id="trend", indicator="ema", period=1,
            data_source="indicator_prices",
        ),
    ]

    def generate_signals(self, context, data):
        trace = DecisionTrace.of(
            DecisionTraceEntry("trend.value", -999, group="indicators"),
            DecisionTraceEntry("custom", True, group="indicators"),
            DecisionTraceEntry("score", 10, group="decision"),
        )
        self.record_decision_trace(trace, symbol="BTC")
        self.record_decision_trace(trace, symbol="BTC")
        context.record(unrelated_metric=123)
        return iter(())


class IndicatorSnapshotSignalStrategy(IndicatorSnapshotStrategy):
    def generate_signals(self, context, data):
        trace = DecisionTrace.of(
            DecisionTraceEntry("signal_only", 7, group="indicators"),
        )
        yield Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG,
        ).with_decision_trace(trace)


class ConfluenceSnapshotStrategy(ConfluenceScoringStrategy):
    schedule = IndicatorSnapshotStrategy.schedule
    symbols = ["BTC"]
    data_sources = IndicatorSnapshotStrategy.data_sources
    indicator_configs = IndicatorSnapshotStrategy.indicator_configs
    confluence_cards = [
        ConfluenceScoreConfig(
            id=name, side=side,
            rules={"price": IndicatorRule(
                "trend", threshold, {"primary": 1}, comparison=comparison,
            )},
            group_thresholds={"primary": 1},
        )
        for name, side, threshold, comparison in (
            ("entry", SignalSide.OPEN_LONG, 0, "le"),
            ("exit", SignalSide.CLOSE_LONG, 200, "ge"),
        )
    ]


class TestDecisionTraceCompatibility(TestCase):
    def test_legacy_report_normalization_and_canonical_precedence(self):
        trace = {"score_card_version": 4, "summary": "Old", "entries": []}
        legacy = {
            "score_cards": [{"symbol": "BTC", **trace}],
            "orders": [{"metadata": {"score_card": trace}}],
            "signals": [{
                "strategy_id": "old",
                "metadata": {"score_card": trace},
            }],
        }
        original = deepcopy(legacy)
        report = RunReport.from_dict(legacy)
        output = report.to_dict()
        self.assertEqual(original, legacy)
        self.assertEqual(output["decision_traces"], output["score_cards"])
        self.assertEqual(4, output["decision_traces"][0][
            "decision_trace_version"
        ])
        for metadata in (
            output["orders"][0]["metadata"],
            output["signals"][0]["metadata"],
        ):
            self.assertEqual(metadata["decision_trace"],
                             metadata["score_card"])
        self.assertEqual(output, RunReport.from_dict(output).to_dict())
        self.assertEqual([], RunReport.from_dict({
            **legacy, "decision_traces": [],
        }).decision_traces)
        report.score_cards = []
        self.assertEqual([], report.decision_traces)

    def test_legacy_database_migration_reload_and_updates(self):
        from sqlalchemy import Column, MetaData, Table, create_engine, inspect
        from sqlalchemy.orm import Session
        from investing_algorithm_framework.infrastructure.database \
            .sql_alchemy import _apply_forward_only_migrations
        from investing_algorithm_framework.infrastructure.models \
            .run_report.run_report import SQLRunReport

        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        old_table = Table("run_reports", MetaData(), *(
            Column(column.name, column.type, primary_key=column.primary_key)
            for column in SQLRunReport.__table__.columns
            if column.name not in ("score_cards_json", "status", "error",
                                   "reason")
        ))
        old_table.create(engine)
        with engine.begin() as connection:
            connection.execute(old_table.insert().values(id=1))
        _apply_forward_only_migrations(engine)
        _apply_forward_only_migrations(engine)
        columns = {item["name"] for item in inspect(engine).get_columns(
            "run_reports"
        )}
        self.assertIn("score_cards_json", columns)
        self.assertNotIn("decision_traces_json", columns)
        legacy = [{"symbol": "BTC", "score_card_version": 3,
                   "summary": "Legacy", "entries": []}]
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO run_reports (id, score_cards_json) VALUES (?, ?)",
                (2, json.dumps(legacy)),
            )
        with Session(engine) as session:
            self.assertEqual([], session.get(SQLRunReport, 1).decision_traces)
            report = session.get(SQLRunReport, 2)
            self.assertEqual("completed", report.status)
            report.update({
                "status": "execution_error", "error": "Test failure",
            })
            session.commit()
            session.expunge_all()
            report = session.get(SQLRunReport, 2)
            self.assertEqual("execution_error", report.to_dict()["status"])
            self.assertEqual("Test failure", report.to_dict()["error"])
            self.assertNotIn("reason", report.to_dict())
            self.assertEqual(3, report.decision_traces[0][
                "decision_trace_version"
            ])
            self.assertEqual(report.decision_traces_json,
                             report.score_cards_json)
            report.update({"decision_traces": [], "score_cards": legacy})
            session.commit()
            session.expunge_all()
            report = session.get(SQLRunReport, 2)
            self.assertEqual([], report.decision_traces)
            report.update({"score_cards": legacy})
            session.commit()
            session.expunge_all()
            report = session.get(SQLRunReport, 2)
            self.assertEqual("Legacy", report.decision_traces[0]["summary"])
            self.assertEqual(report.decision_traces, report.score_cards)


class TestRunReport(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.resource_directory = TemporaryDirectory()
        self.resource_dir = self.resource_directory.name

    def tearDown(self) -> None:
        super().tearDown()
        teardown_sqlalchemy()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
        self.resource_directory.cleanup()

    def _create_app(
        self, strategy_cls=OpenLongOnceStrategy, paper_trading=False,
    ):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE", trading_symbol="EUR",
                initial_balance=1000, paper_trading=paper_trading,
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key=random_string(10),
                secret_key=random_string(10),
            )
        )
        app.add_strategy(strategy_cls)
        return app

    def test_no_run_report_before_run(self):
        app = self._create_app()
        self.assertIsNone(app.get_last_run_report())

    @staticmethod
    def _indicator_prices(close=123.0, start="2020-01-01"):
        return pd.DataFrame({
            "Open": [close], "High": [close], "Low": [close],
            "Close": [close], "Volume": [1],
        }, index=pd.date_range(
            start, periods=1, freq="2h", tz="UTC",
        ))

    def test_indicator_capture_without_signals_deduplicates_trace_values(self):
        app = self._create_app(IndicatorSnapshotStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data",
            return_value=self._indicator_prices(),
        ):
            report = app.run(number_of_iterations=1)
        self.assertEqual([], report["signals"])
        self.assertEqual(2, len(report["indicators"]))
        self.assertEqual(
            {"trend.value": 123.0, "custom": True},
            {item["name"]: item["value"] for item in report["indicators"]},
        )
        for item in report["indicators"]:
            self.assertEqual("IndicatorSnapshotStrategy", item["strategy_id"])
            self.assertEqual("BTC", item["symbol"])
            self.assertIsNotNone(item["timestamp"])
        self.assertEqual(
            report["indicators"], app.get_run_reports()[0]["indicators"],
        )
        self.assertEqual(1, len(report["data_sources"]))
        self.assertEqual(123., report["data_sources"][0]["values"]["Close"])
        self.assertEqual(
            report["data_sources"], app.get_run_reports()[0]["data_sources"],
        )
        self.assertEqual(
            -999,
            report["decision_traces"][0]["entries"][0]["value"],
        )
        json.dumps(report, allow_nan=False)
        app.container.algorithm_runner().disable("Maintenance")
        try:
            disabled = app.run(number_of_iterations=1)
        finally:
            app.container.algorithm_runner().enable()
        self.assertEqual([], disabled["indicators"])
        self.assertEqual([], disabled["data_sources"])
        self.assertEqual([], disabled["confluence_scores"])

    def test_signal_attached_indicator_trace_is_captured(self):
        app = self._create_app(IndicatorSnapshotSignalStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data",
            return_value=self._indicator_prices(),
        ), patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_ticker_data", return_value=None,
        ):
            report = app.run(number_of_iterations=1)
        self.assertEqual(
            {"trend.value": 123.0, "signal_only": 7},
            {item["name"]: item["value"] for item in report["indicators"]},
        )
        self.assertEqual(
            "rejected", report["signals"][0]["status"],
        )

    def test_confluence_cards_are_reported_without_any_emitted_signal(self):
        app = self._create_app(ConfluenceSnapshotStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data", return_value=self._indicator_prices(),
        ):
            report = app.run(number_of_iterations=1)
        self.assertEqual([], report["signals"])
        self.assertEqual({"entry", "exit"}, {
            card["card_id"] for card in report["confluence_scores"]
        })
        for card in report["confluence_scores"]:
            self.assertTrue(card["ready"])
            self.assertFalse(card["qualified"])
            self.assertFalse(card["passed"])
            self.assertEqual("not_emitted", card["signal_status"])
            self.assertEqual("confluence.not_qualified", card["signal_reason"])
            self.assertEqual("ConfluenceSnapshotStrategy", card["strategy_id"])
            self.assertEqual("BTC", card["symbol"])
            self.assertIsNotNone(card["timestamp"])
            self.assertTrue(card["groups"])
            self.assertTrue(card["evaluations"])
        self.assertEqual(
            report["confluence_scores"],
            app.get_run_reports()[0]["confluence_scores"],
        )

    def test_failed_confluence_strategy_keeps_all_already_evaluated_cards(self):
        app = self._create_app(ConfluenceSnapshotStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data", return_value=self._indicator_prices(),
        ), patch.object(
            ConfluenceSnapshotStrategy, "generate_signals",
            side_effect=RuntimeError("Confluence failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Confluence failure"):
                app.run(number_of_iterations=1)
        report = app.get_last_run_report()
        self.assertEqual("execution_error", report["status"])
        self.assertEqual([], report["signals"])
        self.assertEqual(2, len(report["confluence_scores"]))
        self.assertTrue(all(
            card["signal_status"] == "unknown"
            and card["signal_reason"] == "strategy.execution_incomplete"
            for card in report["confluence_scores"]
        ))
        self.assertEqual(123., report["data_sources"][0]["values"]["Close"])

    def test_warmup_confluence_cards_and_sources_are_not_dropped(self):
        app = self._create_app(ConfluenceSnapshotStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data",
            return_value=self._indicator_prices().iloc[:0],
        ):
            report = app.run(number_of_iterations=1)
        self.assertEqual([], report["signals"])
        self.assertEqual(2, len(report["confluence_scores"]))
        self.assertTrue(all(
            not card["ready"] for card in report["confluence_scores"]
        ))
        self.assertTrue(all(
            card["signal_status"] == "not_emitted"
            and card["signal_reason"] == "confluence.indicators_not_ready"
            for card in report["confluence_scores"]
        ))
        self.assertEqual({}, report["data_sources"][0]["values"])
        self.assertIsNone(report["data_sources"][0]["source_timestamp"])
        self.assertEqual(None, report["indicators"][0]["value"])

    def test_bounded_report_keeps_every_tick_and_strategy_indicator(self):
        app = self._create_app(IndicatorSnapshotStrategy)
        app.add_strategy(IndicatorSnapshotSignalStrategy)
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data",
            return_value=self._indicator_prices(),
        ), patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_ticker_data", return_value=None,
        ), patch("investing_algorithm_framework.app.eventloop.sleep"):
            with patch(
                "investing_algorithm_framework.app.eventloop.EventLoopService."
                "_get_due_strategies",
                new=lambda loop, now: loop.strategies,
            ):
                report = app.run(number_of_iterations=2)
        self.assertEqual(8, len(report["indicators"]))
        self.assertEqual(4, len(report["data_sources"]))
        self.assertEqual(2, len({
            item["timestamp"] for item in report["indicators"]
        }))
        self.assertEqual(
            set(report["strategy_ids"]),
            {item["strategy_id"] for item in report["indicators"]},
        )

    def test_failed_tick_keeps_only_its_evaluated_indicator_values(self):
        app = self._create_app(IndicatorSnapshotStrategy)

        def run_then_fail(loop, **kwargs):
            loop._run_iteration(loop.strategies, tasks=[])
            with patch.object(IndicatorSnapshotStrategy, "generate_signals",
                              side_effect=RuntimeError("Indicator failure")):
                loop._run_iteration(loop.strategies, tasks=[])

        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_data",
            side_effect=[self._indicator_prices(100),
                         self._indicator_prices(200, "2020-01-01T02:00:00")],
        ), patch(
            "investing_algorithm_framework.app.app.EventLoopService.start",
            new=run_then_fail,
        ):
            with self.assertRaisesRegex(RuntimeError, "Indicator failure"):
                app.run()
        failed, previous = app.get_run_reports()
        self.assertEqual("execution_error", failed["status"])
        self.assertEqual([], failed["signals"])
        self.assertEqual(["trend.value"], [
            item["name"] for item in failed["indicators"]
        ])
        self.assertEqual(200, failed["indicators"][0]["value"])
        self.assertEqual(100, previous["indicators"][0]["value"])
        self.assertEqual(200, failed["data_sources"][0]["values"]["Close"])
        self.assertEqual(100, previous["data_sources"][0]["values"]["Close"])
        failed["indicators"][0]["value"] = -1
        self.assertEqual(
            200, app.get_run_reports()[0]["indicators"][0]["value"],
        )

    def test_multi_strategy_report_keeps_shared_snapshot_and_attribution(self):
        app = self._create_app(NoSignalDecisionTraceStrategy)
        app.add_strategy(NoSignalScoreCardStrategy)
        report = app.run(number_of_iterations=1)
        self.assertEqual(
            ["NoSignalDecisionTraceStrategy", "NoSignalScoreCardStrategy"],
            report["strategy_ids"],
        )
        self.assertEqual(1, len(app.get_run_reports()))
        self.assertEqual(
            set(report["strategy_ids"]),
            {entry["strategy_id"] for entry in report["decision_traces"]},
        )

    def test_interruption_reports_specific_status_without_duplicate(self):
        for expected_count, iterations in enumerate((1, None), 1):
            app = self._create_app(NoSignalDecisionTraceStrategy)
            with patch.object(NoSignalDecisionTraceStrategy,
                              "generate_signals",
                              side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    app.run(number_of_iterations=iterations)
            report = app.get_last_run_report()
            self.assertEqual("interrupted", report["status"])
            self.assertEqual("Interrupted", report["error"])
            self.assertEqual(report, app.get_run_reports()[0])
            self.assertEqual(expected_count, len(app.get_run_reports()))

    def test_bounded_run_returns_report_and_failure_replaces_it(self):
        app = self._create_app(NoSignalDecisionTraceStrategy)
        with patch("investing_algorithm_framework.app.eventloop.sleep"):
            report = app.run(number_of_iterations=1)
        self.assertEqual(report, app.get_last_run_report())
        self.assertEqual("completed", report["status"])
        with patch.object(NoSignalDecisionTraceStrategy, "generate_signals",
                          side_effect=RuntimeError("Strategy failed")):
            with self.assertRaisesRegex(RuntimeError, "Strategy failed"):
                app.run(number_of_iterations=1)
        failed = app.get_last_run_report()
        self.assertNotEqual(report["id"], failed["id"])
        self.assertEqual("execution_error", failed["status"])
        self.assertEqual("Strategy failed", failed["error"])
        self.assertEqual(failed, app.get_run_reports()[0])

    def test_disabled_and_not_due_runs_return_skipped_reports(self):
        app = self._create_app(
            NoSignalDecisionTraceStrategy, paper_trading=True)
        with patch("investing_algorithm_framework.app.eventloop.sleep"):
            report = app.run(number_of_iterations=1,
                             run_immediately_on_start=False)
        self.assertEqual("no_strategy_due", report["status"])
        self.assertEqual("PAPER", report["environment"])
        app.container.algorithm_runner().disable("Maintenance")
        try:
            skipped = app.run(number_of_iterations=1)
        finally:
            app.container.algorithm_runner().enable()
        self.assertEqual("algorithm_disabled", skipped["status"])
        self.assertEqual(
            ["NoSignalDecisionTraceStrategy"], skipped["strategy_ids"],
        )
        self.assertNotEqual(report["id"], skipped["id"])
        self.assertEqual(skipped, app.get_run_reports()[0])

    def test_canonical_recording_appears_in_tick_and_top_level_report(self):
        app = self._create_app(strategy_cls=NoSignalDecisionTraceStrategy)
        app.run(number_of_iterations=1)
        report = app.get_last_run_report()
        self.assertEqual(report["decision_traces"], report["score_cards"])
        self.assertEqual(1, len(report["decision_traces"]))
        self.assertEqual(1, report["decision_traces"][0][
            "decision_trace_version"
        ])
        self.assertEqual([], report["signals"])
        self.assertEqual("No entry", report["decision_traces"][0]["summary"])

    def test_scheduled_no_signal_reports_are_isolated_without_stop_duplicate(
        self,
    ):
        app = self._create_app(
            NoSignalDecisionTraceStrategy, paper_trading=True)

        def run_two_ticks(loop, **kwargs):
            for iteration in range(2):
                loop._run_iteration(loop.strategies, tasks=[])

        with patch("investing_algorithm_framework.app.app.EventLoopService."
                   "start", new=run_two_ticks):
            report = app.run()
        reports = app.get_run_reports()
        self.assertEqual(2, len(reports))
        self.assertEqual(reports[0], report)
        self.assertNotEqual(reports[0]["started_at"], reports[1]["started_at"])
        for report in reports:
            self.assertEqual("completed", report["status"])
            self.assertEqual("PAPER", report["environment"])
            self.assertEqual([], report["signals"])
            self.assertEqual(1, len(report["decision_traces"]))

    def test_scheduled_failure_does_not_include_previous_tick_signals(self):
        app = self._create_app(NoSignalDecisionTraceStrategy)

        def run_then_fail(loop, **kwargs):
            loop._run_iteration(loop.strategies, tasks=[])
            with patch.object(NoSignalDecisionTraceStrategy,
                              "generate_signals",
                              side_effect=RuntimeError("Tick failed")):
                loop._run_iteration(loop.strategies, tasks=[])

        with patch("investing_algorithm_framework.app.app.EventLoopService."
                   "start", new=run_then_fail):
            with self.assertRaisesRegex(RuntimeError, "Tick failed"):
                app.run()
        reports = app.get_run_reports()
        self.assertEqual(2, len(reports))
        self.assertEqual("execution_error", reports[0]["status"])
        self.assertEqual("Tick failed", reports[0]["error"])
        self.assertEqual([], reports[0]["signals"])
        self.assertEqual([], reports[0]["decision_traces"])
        self.assertEqual(reports[0], app.get_last_run_report())

    def test_manual_wait_returns_requested_tick_not_previous_report(self):
        app = self._create_app(
            NoSignalDecisionTraceStrategy, paper_trading=True)

        def run_manual(loop, *args):
            loop._run_iteration(loop.strategies, tasks=[])
            previous = app.get_last_run_report()
            runner = AlgorithmRunner()
            runner.configure(loop)
            runner._status = RUNNING
            queued = Event()
            original_request = loop.request_immediate_run

            def enqueue(strategy_ids):
                completion = original_request(strategy_ids)
                queued.set()
                return completion

            with patch.object(loop, "request_immediate_run", new=enqueue):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    waiting = executor.submit(
                        runner.invoke_now, wait=True, timeout=5)
                    self.assertTrue(queued.wait(5))
                    strategies = loop._pop_immediate_strategies(
                        loop._configuration_service.config["INDEX_DATETIME"])
                    report = loop._run_iteration(strategies, tasks=[])
                    self.assertEqual(report, waiting.result(timeout=5))
            self.assertNotEqual(previous["id"], report["id"])
            self.assertEqual("completed", report["status"])
            self.assertEqual([], report["signals"])

        with patch("investing_algorithm_framework.app.app.EventLoopService."
                   "_start", new=run_manual):
            app.run()
        self.assertEqual(2, len(app.get_run_reports()))

    def test_manual_timeout_does_not_cancel_and_failure_resolves_requests(
        self,
    ):
        app = self._create_app(NoSignalDecisionTraceStrategy)

        def run_manual(loop, *args):
            runner = AlgorithmRunner()
            runner.configure(loop)
            runner._status = RUNNING
            with self.assertRaises(TimeoutError):
                runner.invoke_now(wait=True, timeout=0.001)
            with self.assertRaises(OperationalException):
                runner.invoke_now(["missing"], wait=True)
            for timeout in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    runner.invoke_now(wait=True, timeout=timeout)
            completion = loop.request_immediate_run()
            strategies = loop._pop_immediate_strategies(
                loop._configuration_service.config["INDEX_DATETIME"])
            with patch.object(NoSignalDecisionTraceStrategy,
                              "generate_signals",
                              side_effect=RuntimeError("Manual failure")):
                with self.assertRaisesRegex(RuntimeError, "Manual failure"):
                    loop._run_iteration(strategies, tasks=[])
            report = completion.result(timeout=1)
            self.assertEqual("execution_error", report["status"])
            self.assertEqual("Manual failure", report["error"])
            self.assertEqual(report, app.get_last_run_report())
            self.assertEqual(1, len(app.get_run_reports()))

        with patch("investing_algorithm_framework.app.app.EventLoopService."
                   "_start", new=run_manual):
            app.run()

    def test_stop_records_skipped_queued_request(self):
        app = self._create_app(NoSignalDecisionTraceStrategy)
        requests = []

        def queue_then_stop(loop, *args):
            requests.append(loop.request_immediate_run())
            loop.request_stop()

        with patch("investing_algorithm_framework.app.app.EventLoopService."
                   "_start", new=queue_then_stop):
            report = app.run()
        self.assertEqual(report, requests[0].result(timeout=1))
        self.assertEqual("loop_stopped", report["status"])
        self.assertEqual(1, len(app.get_run_reports()))

    def test_state_handler_saves_failure_report_after_persistence(self):
        app = self._create_app(NoSignalDecisionTraceStrategy)
        state_handler = Mock()
        app._state_handler = state_handler
        saved_reports = []

        def save_reports(directory):
            saved_reports.append(app.get_run_reports())

        state_handler.save.side_effect = save_reports
        with patch.object(NoSignalDecisionTraceStrategy, "generate_signals",
                          side_effect=RuntimeError("Save my failure")):
            with self.assertRaisesRegex(RuntimeError, "Save my failure"):
                app.run(number_of_iterations=1)
        self.assertEqual(1, len(saved_reports))
        self.assertEqual("execution_error", saved_reports[0][0]["status"])
        self.assertIsNotNone(saved_reports[0][0]["algorithm_id"])

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_run_report_includes_created_order_and_approved_signal(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app()
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertIsNotNone(report)
        self.assertIsNotNone(report["id"])
        self.assertEqual(1, report["number_of_iterations"])
        self.assertIsNotNone(report["started_at"])
        self.assertIsNotNone(report["completed_at"])
        self.assertEqual(1, len(report["orders"]))
        self.assertEqual("BTC", report["orders"][0]["target_symbol"])
        self.assertEqual(
            "OpenLongOnceStrategy", report["orders"][0]["strategy_id"]
        )

        all_signals = report["signals"]
        self.assertEqual(1, len(all_signals))
        self.assertEqual("approved", all_signals[0]["status"])
        self.assertIsNone(all_signals[0]["reason"])
        self.assertEqual("OpenLongOnceStrategy", all_signals[0]["strategy_id"])
        self.assertIsNotNone(all_signals[0]["timestamp"])

        self.assertEqual(1, len(report["portfolios"]))
        self.assertGreaterEqual(len(report["positions"]), 1)

        self.assertEqual("PROD", report["environment"])
        self.assertEqual(["OpenLongOnceStrategy"], report["strategy_ids"])
        self.assertNotIn("is_paper", report)
        self.assertNotIn("reason", report)
        portfolio = report["portfolios"][0]
        for field_name in (
            "net_size", "realized", "total_revenue", "total_cost",
            "total_net_gain", "total_trade_volume",
        ):
            self.assertIn(field_name, portfolio)

        # The report must be persisted: a fresh query through the
        # run_report_service (a new repository read, not the
        # in-process cached object) must return the same report.
        run_report_service = app.container.run_report_service()
        persisted = run_report_service.get(report["id"])
        self.assertEqual(1, len(persisted.orders))
        self.assertEqual("BTC", persisted.orders[0]["target_symbol"])

        history = app.get_run_reports()
        self.assertEqual(1, len(history))
        self.assertEqual(report["id"], history[0]["id"])

    def test_run_report_includes_rejected_signal_with_reason(self):
        # Ticker data resolves to None, so get_latest_price() returns
        # None and SizePositionsPhase drops the signal with a clear
        # reason instead of sizing it into an order.
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_ticker_data",
            return_value=None,
        ):
            app = self._create_app()
            app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual(0, len(report["orders"]))

        all_signals = report["signals"]
        self.assertEqual(1, len(all_signals))
        self.assertEqual("rejected", all_signals[0]["status"])
        self.assertEqual(
            "size_positions.no_price", all_signals[0]["reason"]
        )

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_score_card_survives_on_a_filled_order(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app(strategy_cls=ScoreCardStrategy)
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual(1, len(report["orders"]))
        score_card = report["orders"][0]["metadata"]["score_card"]
        self.assertEqual(score_card, report["orders"][0]["metadata"][
            "decision_trace"
        ])
        self.assertEqual("RSI oversold", score_card["summary"])
        self.assertEqual(
            28.4, score_card["entries"][0]["value"]
        )

        all_signals = report["signals"]
        self.assertEqual(
            score_card, all_signals[0]["metadata"]["score_card"]
        )

    def test_score_card_survives_on_a_rejected_signal(self):
        with patch(
            "investing_algorithm_framework.services.data_providers."
            "DataProviderService.get_ticker_data",
            return_value=None,
        ):
            app = self._create_app(strategy_cls=ScoreCardStrategy)
            app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual(0, len(report["orders"]))

        all_signals = report["signals"]
        self.assertEqual("rejected", all_signals[0]["status"])
        score_card = all_signals[0]["metadata"]["score_card"]
        self.assertEqual(score_card, all_signals[0]["metadata"][
            "decision_trace"
        ])
        self.assertEqual("RSI oversold", score_card["summary"])
        self.assertEqual("rsi_14", score_card["entries"][0]["name"])

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_score_card_recorded_when_no_signal_is_generated(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app(strategy_cls=NoSignalScoreCardStrategy)
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual(0, len(report["orders"]))

        self.assertEqual([], report["signals"])
        self.assertEqual(1, len(report["decision_traces"]))
        self.assertEqual("BTC", report["decision_traces"][0]["symbol"])
        self.assertEqual(
            "RSI neutral - no signal",
            report["decision_traces"][0]["summary"],
        )

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_environment_is_paper_when_all_portfolios_are_paper_traded(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app(paper_trading=True)
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual("PAPER", report["environment"])

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_report_has_top_level_score_cards(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app(strategy_cls=NoSignalScoreCardStrategy)
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertEqual(1, len(report["score_cards"]))
        score_card = report["score_cards"][0]
        self.assertEqual("BTC", score_card["symbol"])
        self.assertEqual(
            "NoSignalScoreCardStrategy", score_card["strategy_id"]
        )
        self.assertEqual("RSI neutral - no signal", score_card["summary"])
        self.assertEqual("rsi_14", score_card["entries"][0]["name"])

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ohlcv_data"
    )
    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_run_report_includes_orders_updated_this_run(
        self, mock_get_ticker, mock_get_ohlcv
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        mock_get_ohlcv.return_value = None
        OpenLongOnceEverStrategy._fired = False
        app = self._create_app(strategy_cls=OpenLongOnceEverStrategy)
        app.run(number_of_iterations=1)

        first_report = app.get_last_run_report()
        self.assertEqual(1, len(first_report["orders"]))
        order_id = first_report["orders"][0]["id"]
        self.assertEqual("OPEN", first_report["orders"][0]["status"])

        # Second run yields no new signal, so the only reason the
        # order from the first run should reappear is that the
        # pending-order check filled it (updated_at, not created_at,
        # falls inside this run's window).
        app.run(number_of_iterations=1)
        second_report = app.get_last_run_report()

        updated_order = next(
            (o for o in second_report["orders"] if o["id"] == order_id),
            None,
        )
        self.assertIsNotNone(updated_order)
        self.assertEqual("CLOSED", updated_order["status"])

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ohlcv_data"
    )
    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_run_report_includes_still_open_untouched_order(
        self, mock_get_ticker, mock_get_ohlcv
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        mock_get_ohlcv.return_value = None
        OpenLongOnceEverStrategy._fired = False
        app = self._create_app(strategy_cls=OpenLongOnceEverStrategy)
        app.run(number_of_iterations=1)

        first_report = app.get_last_run_report()
        self.assertEqual(1, len(first_report["orders"]))
        order_id = first_report["orders"][0]["id"]
        self.assertEqual("OPEN", first_report["orders"][0]["status"])

        # Second run: no new signal, and the pending-order check is
        # stubbed out so nothing touches the order at all — both
        # created_at and updated_at fall before this run's window.
        # It must still appear in the report solely because it is
        # still OPEN at the venue, not because anything changed.
        with patch(
            "investing_algorithm_framework.services.order_service."
            "order_service.OrderService.check_pending_orders"
        ):
            app.run(number_of_iterations=1)

        second_report = app.get_last_run_report()
        still_open_order = next(
            (o for o in second_report["orders"] if o["id"] == order_id),
            None,
        )
        self.assertIsNotNone(still_open_order)
        self.assertEqual("OPEN", still_open_order["status"])
