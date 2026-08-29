import os
import shutil
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    MarketCredential, Schedule, PositionSize, Signal, SignalSide, \
    ScoreCard, ScoreCardEntry
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from tests.resources import random_string, OrderExecutorTest, \
    PortfolioProviderTest


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


class TestRunReport(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "resources"
            )
        )

    def tearDown(self) -> None:
        super().tearDown()
        teardown_sqlalchemy()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def _create_app(self, strategy_cls=OpenLongOnceStrategy, paper_trading=False):
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

