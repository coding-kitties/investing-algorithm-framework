import os
import threading
import time

from investing_algorithm_framework import MarketCredential, \
    PortfolioConfiguration, Schedule, TimeUnit, TradingStrategy
from investing_algorithm_framework.app.algorithm_runner import (
    AlgorithmRunner, NOT_STARTED, RUNNING, STOPPED, CONTROL_FILE_NAME,
)
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.domain import OperationalException
from investing_algorithm_framework.services import \
    BacktestTradeOrderEvaluator
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestEventLoopServiceStop(TestBase):
    """
    Covers the live (unbounded) branch of ``EventLoopService.start()``:
    it must actually keep looping until ``request_stop()`` is called,
    instead of running a single iteration and returning.
    """
    market_credentials = [
        MarketCredential(
            market="BITVAVO", api_key="api_key", secret_key="secret_key",
        )
    ]
    external_balances = {"EUR": 1000}
    portfolio_configurations = [
        PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
    ]

    def _build_event_loop_service(self):
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service(),
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container
            .portfolio_snapshot_service(),
        )
        self.app.add_strategy(StrategyOne())
        event_loop_service.initialize(
            algorithm=self.app.get_algorithm(),
            trade_order_evaluator=BacktestTradeOrderEvaluator(
                trade_service=self.app.container.trade_service(),
                order_service=self.app.container.order_service(),
                trade_stop_loss_service=self.app.container
                .trade_stop_loss_service(),
                trade_take_profit_service=self.app.container
                .trade_take_profit_service(),
            ),
        )
        return event_loop_service

    def test_live_loop_keeps_running_until_stopped(self):
        event_loop_service = self._build_event_loop_service()

        thread = threading.Thread(
            target=event_loop_service.start, kwargs={}, daemon=True
        )
        thread.start()
        # Let it run a couple of iterations (sleeps ~1s between them).
        time.sleep(2.5)
        self.assertTrue(thread.is_alive())

        event_loop_service.request_stop()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_reset_stop_allows_restarting(self):
        event_loop_service = self._build_event_loop_service()
        event_loop_service.request_stop()
        self.assertTrue(event_loop_service.stop_requested)
        event_loop_service.reset_stop()
        self.assertFalse(event_loop_service.stop_requested)


class TestAlgorithmRunner(TestBase):
    market_credentials = [
        MarketCredential(
            market="BITVAVO", api_key="api_key", secret_key="secret_key",
        )
    ]
    external_balances = {"EUR": 1000}
    portfolio_configurations = [
        PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
    ]

    def _build_event_loop_service(self):
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service(),
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container
            .portfolio_snapshot_service(),
        )
        self.app.add_strategy(StrategyOne())
        event_loop_service.initialize(
            algorithm=self.app.get_algorithm(),
            trade_order_evaluator=BacktestTradeOrderEvaluator(
                trade_service=self.app.container.trade_service(),
                order_service=self.app.container.order_service(),
                trade_stop_loss_service=self.app.container
                .trade_stop_loss_service(),
                trade_take_profit_service=self.app.container
                .trade_take_profit_service(),
            ),
        )
        return event_loop_service

    def test_start_without_configure_raises(self):
        runner = AlgorithmRunner()
        with self.assertRaises(OperationalException):
            runner.start()

    def test_start_stop_lifecycle(self):
        runner = AlgorithmRunner()
        self.assertEqual(NOT_STARTED, runner.status)

        event_loop_service = self._build_event_loop_service()
        runner.configure(event_loop_service)

        started = runner.start()
        self.assertTrue(started)
        self.assertEqual(RUNNING, runner.status)

        # Starting again while already running is a no-op.
        self.assertFalse(runner.start())

        stopped = runner.stop(wait=True, timeout=5)
        self.assertTrue(stopped)
        self.assertEqual(STOPPED, runner.status)

        report = runner.get_status_report()
        self.assertIsNotNone(report["started_at"])
        self.assertIsNotNone(report["stopped_at"])

    def test_stop_when_not_running_is_noop(self):
        runner = AlgorithmRunner()
        self.assertFalse(runner.stop())


class _CountingStrategy(TradingStrategy):
    """Strategy that records how many times it actually ran, used to
    verify ``App.run()`` skips its iteration entirely when disabled."""
    schedule = Schedule.every(1, TimeUnit.SECOND)
    call_count = 0

    def run_strategy(self, context, data):
        _CountingStrategy.call_count += 1


class TestAlgorithmControlPersistence(TestBase):
    """
    Covers the persisted enabled/disabled control flag: what makes
    start/stop meaningful for stateless deployments (AWS Lambda, Azure
    Functions), since each invocation is a fresh ``App.run()`` call
    with no in-process state to carry the flag across invocations —
    only the resource directory (which a state handler round-trips)
    does.
    """
    market_credentials = [
        MarketCredential(
            market="BITVAVO", api_key="api_key", secret_key="secret_key",
        )
    ]
    external_balances = {"EUR": 1000}
    portfolio_configurations = [
        PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
    ]

    def setUp(self) -> None:
        super().setUp()
        _CountingStrategy.call_count = 0

    def tearDown(self) -> None:
        control_file = os.path.join(
            self.resource_directory, CONTROL_FILE_NAME
        )
        if os.path.exists(control_file):
            os.remove(control_file)
        super().tearDown()

    def test_enabled_by_default(self):
        runner = AlgorithmRunner()
        runner.bind_persistence(self.app.resource_directory_path)
        self.assertTrue(runner.is_enabled())
        state = runner.get_control_state()
        self.assertTrue(state["enabled"])
        self.assertIsNone(state["reason"])

    def test_disable_and_enable_persist_across_instances(self):
        first = AlgorithmRunner()
        first.bind_persistence(self.app.resource_directory_path)
        first.disable(reason="maintenance")

        # A brand new runner bound to the same resource directory
        # (simulating a fresh process/invocation) must see the same
        # persisted state.
        second = AlgorithmRunner()
        second.bind_persistence(self.app.resource_directory_path)
        self.assertFalse(second.is_enabled())
        self.assertEqual(
            "maintenance", second.get_control_state()["reason"]
        )

        second.enable()
        self.assertTrue(first.is_enabled())

    def test_app_start_stop_algorithm_without_live_loop(self):
        # No `run()` has happened yet in this process, so there is no
        # in-process loop to (re)start/stop — only the persisted flag.
        self.assertTrue(self.app.is_algorithm_enabled())

        started = self.app.stop_algorithm(reason="paused for testing")
        self.assertFalse(started)
        self.assertFalse(self.app.is_algorithm_enabled())
        self.assertEqual(
            "paused for testing",
            self.app.get_algorithm_control_state()["reason"],
        )

        resumed = self.app.start_algorithm()
        self.assertFalse(resumed)
        self.assertTrue(self.app.is_algorithm_enabled())

    def test_run_skips_entirely_when_disabled(self):
        self.app.add_strategy(_CountingStrategy())

        self.app.stop_algorithm(reason="disabled before first run")
        self.app.run(number_of_iterations=1)
        self.assertEqual(0, _CountingStrategy.call_count)

        self.app.start_algorithm()
        self.app.run(number_of_iterations=1)
        self.assertEqual(1, _CountingStrategy.call_count)
