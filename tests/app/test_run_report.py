import os
import shutil
import json
from tempfile import TemporaryDirectory
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    MarketCredential, Schedule, PositionSize, Signal, SignalSide, \
    ScoreCard, ScoreCardEntry, DecisionTrace, DecisionTraceEntry, RunReport
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


class TestDecisionTraceCompatibility(TestCase):
    def test_legacy_report_normalization_and_canonical_precedence(self):
        trace = {"score_card_version": 4, "summary": "Old", "entries": []}
        legacy = {
            "score_cards": [{"symbol": "BTC", **trace}],
            "orders": [{"metadata": {"score_card": trace}}],
            "signals": [{
                "strategy_id": "old",
                "score_cards": [{"symbol": "BTC", "score_card": trace}],
                "signals": [{"metadata": {"score_card": trace}}],
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
            output["signals"][0]["signals"][0]["metadata"],
            output["signals"][0]["decision_traces"][0],
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
            report.update({"status": "failed", "error": "Test failure",
                           "reason": "strategy_error"})
            session.commit()
            session.expunge_all()
            report = session.get(SQLRunReport, 2)
            self.assertEqual("failed", report.to_dict()["status"])
            self.assertEqual("Test failure", report.to_dict()["error"])
            self.assertEqual("strategy_error", report.to_dict()["reason"])
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
        self.assertEqual("failed", failed["status"])
        self.assertEqual("Strategy failed", failed["error"])
        self.assertEqual(failed, app.get_run_reports()[0])

    def test_disabled_and_not_due_runs_return_skipped_reports(self):
        app = self._create_app(
            NoSignalDecisionTraceStrategy, paper_trading=True)
        with patch("investing_algorithm_framework.app.eventloop.sleep"):
            report = app.run(number_of_iterations=1,
                             run_immediately_on_start=False)
        self.assertEqual("skipped", report["status"])
        self.assertEqual("no_strategy_due", report["reason"])
        self.assertTrue(report["is_paper"])
        app.container.algorithm_runner().disable("Maintenance")
        try:
            skipped = app.run(number_of_iterations=1)
        finally:
            app.container.algorithm_runner().enable()
        self.assertEqual("skipped", skipped["status"])
        self.assertEqual("algorithm_disabled", skipped["reason"])
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
        tick = report["signals"][0]
        self.assertEqual(tick["decision_traces"], tick["score_cards"])
        self.assertEqual("No entry", tick["decision_traces"][0][
            "decision_trace"
        ]["summary"])

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
            self.assertTrue(report["is_paper"])
            self.assertEqual(1, len(report["signals"]))
            self.assertEqual([], report["signals"][0]["signals"])
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
        self.assertEqual("failed", reports[0]["status"])
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
            self.assertEqual(1, len(report["signals"]))

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
            self.assertEqual("failed", report["status"])
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
        self.assertEqual("skipped", report["status"])
        self.assertEqual("loop_stopped", report["reason"])
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
        self.assertEqual("failed", saved_reports[0][0]["status"])
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

        all_signals = [
            s for entry in report["signals"] for s in entry["signals"]
        ]
        self.assertEqual(1, len(all_signals))
        self.assertEqual("approved", all_signals[0]["status"])
        self.assertIsNone(all_signals[0]["reason"])

        self.assertEqual(1, len(report["portfolios"]))
        self.assertGreaterEqual(len(report["positions"]), 1)

        self.assertFalse(report["is_paper"])
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

        all_signals = [
            s for entry in report["signals"] for s in entry["signals"]
        ]
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

        all_signals = [
            s for entry in report["signals"] for s in entry["signals"]
        ]
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

        all_signals = [
            s for entry in report["signals"] for s in entry["signals"]
        ]
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

        entry = report["signals"][0]
        self.assertEqual([], entry["signals"])
        self.assertEqual(1, len(entry["score_cards"]))
        self.assertEqual("BTC", entry["score_cards"][0]["symbol"])
        self.assertEqual(
            "RSI neutral - no signal",
            entry["score_cards"][0]["score_card"]["summary"],
        )

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data"
    )
    def test_is_paper_true_when_all_portfolios_are_paper_traded(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        app = self._create_app(paper_trading=True)
        app.run(number_of_iterations=1)

        report = app.get_last_run_report()
        self.assertTrue(report["is_paper"])

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
