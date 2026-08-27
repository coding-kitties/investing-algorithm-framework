import os
import shutil
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, RESOURCE_DIRECTORY, Schedule, Signal, SignalSide, \
    PositionSize, OperationalException, PaperTradingMode, Order, \
    Portfolio
from investing_algorithm_framework.domain import ImproperlyConfigured
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from investing_algorithm_framework.infrastructure import (
    PaperTradingOrderExecutor, PaperTradingPortfolioProvider,
    CCXTOrderExecutor, CCXTPortfolioProvider,
)


class OpenLongOnceStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=50.0)
    ]

    def generate_signals(self, context, data):
        yield Signal(symbol="BTC", side=SignalSide.OPEN_LONG)


class FireOnceStrategy(TradingStrategy):
    """Signals exactly once across the process lifetime, so a second
    ``app.run()`` call doesn't place a second order for the same
    symbol while the first is still pending confirmation."""
    schedule = Schedule.every(2, TimeUnit.SECOND)
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=50.0)
    ]
    _fired = False

    def generate_signals(self, context, data):
        if FireOnceStrategy._fired:
            return
        FireOnceStrategy._fired = True
        yield Signal(symbol="BTC", side=SignalSide.OPEN_LONG)


class TestPaperTradingComponents(TestCase):
    """Unit tests for the local paper-trading executor/provider,
    with no app involved."""

    def test_supports_market_is_scoped(self):
        executor = PaperTradingOrderExecutor(markets=["BINANCE"])
        self.assertTrue(executor.supports_market("binance"))
        self.assertFalse(executor.supports_market("KRAKEN"))

    def test_execute_order_leaves_order_open_pending_confirmation(self):
        executor = PaperTradingOrderExecutor(markets=["BINANCE"])
        order = Order(
            order_type="LIMIT", order_side="BUY", amount=1,
            target_symbol="BTC", trading_symbol="EUR", price=100,
        )
        result = executor.execute_order(
            portfolio=None, order=order, market_credential=None
        )
        self.assertEqual(0, result.filled)
        self.assertEqual(1, result.remaining)
        self.assertEqual("OPEN", result.status)
        self.assertTrue(result.external_id.startswith("paper-"))

    def test_cancel_order_while_open_succeeds(self):
        executor = PaperTradingOrderExecutor(markets=["BINANCE"])
        order = Order(
            order_type="LIMIT", order_side="BUY", amount=1,
            target_symbol="BTC", trading_symbol="EUR", price=100,
        )
        placed = executor.execute_order(
            portfolio=None, order=order, market_credential=None
        )
        canceled = executor.cancel_order(
            portfolio=None, order=placed, market_credential=None
        )
        self.assertEqual("CANCELED", canceled.status)

    def test_cancel_order_after_fill_raises(self):
        executor = PaperTradingOrderExecutor(markets=["BINANCE"])
        order = Order(
            order_type="LIMIT", order_side="BUY", amount=1,
            target_symbol="BTC", trading_symbol="EUR", price=100,
        )
        filled = executor.execute_order(
            portfolio=None, order=order, market_credential=None
        )
        filled.status = "CLOSED"
        with self.assertRaises(OperationalException):
            executor.cancel_order(
                portfolio=None, order=filled, market_credential=None
            )

    def test_provider_get_position_returns_initial_balance(self):
        provider = PaperTradingPortfolioProvider(markets=["BINANCE"])
        portfolio = Portfolio(
            identifier="test", trading_symbol="EUR", net_size=500,
            unallocated=500, initial_balance=500, market="BINANCE",
        )
        portfolio.id = 1
        position = provider.get_position(portfolio, "EUR", None)
        self.assertEqual(500, position.amount)

    def test_provider_get_order_returns_order_unchanged(self):
        provider = PaperTradingPortfolioProvider(markets=["BINANCE"])
        order = Order(
            order_type="LIMIT", order_side="BUY", amount=1,
            target_symbol="BTC", trading_symbol="EUR", price=100,
        )
        self.assertIs(
            order, provider.get_order(None, order, None)
        )


class TestPaperTradingApp(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "resources"
            )
        )

    def tearDown(self) -> None:
        teardown_sqlalchemy()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def test_local_paper_trading_requires_initial_balance(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        with self.assertRaisesRegex(
            ImproperlyConfigured, "requires an initial_balance"
        ):
            app.add_market(
                market="BINANCE",
                trading_symbol="EUR",
                paper_trading=True,
                paper_trading_mode=PaperTradingMode.LOCAL,
            )

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data",
        return_value={"symbol": "BTCEUR", "ask": 100, "bid": 90},
    )
    def test_local_paper_trading_orders_left_open_without_real_credentials(
        self, _
    ):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="BINANCE",
            trading_symbol="EUR",
            initial_balance=1000,
            paper_trading=True,
            paper_trading_mode=PaperTradingMode.LOCAL,
        )
        app.add_strategy(OpenLongOnceStrategy)

        app.run(number_of_iterations=1)

        orders = app.container.order_service().get_all()
        self.assertEqual(1, len(orders))
        # Left OPEN — PaperTradingOrderExecutor no longer instant-fills;
        # DefaultTradeOrderEvaluator only confirms the fill once an
        # OHLCV bar for the order's symbol touches its price, which
        # can't happen within the same iteration the order was placed.
        self.assertEqual("OPEN", orders[0].status)
        self.assertTrue(orders[0].external_id.startswith("paper-"))

        portfolios = app.container.portfolio_service().get_all()
        self.assertEqual(1, len(portfolios))
        self.assertEqual("BINANCE", portfolios[0].market)

    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ohlcv_data"
    )
    @patch(
        "investing_algorithm_framework.services.data_providers."
        "DataProviderService.get_ticker_data",
        return_value={"symbol": "BTCEUR", "ask": 100, "bid": 90},
    )
    def test_local_paper_trading_confirms_fill_against_ohlcv(
        self, _, mock_get_ohlcv
    ):
        import polars as pl
        from datetime import timedelta

        FireOnceStrategy._fired = False
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="BINANCE",
            trading_symbol="EUR",
            initial_balance=1000,
            paper_trading=True,
            paper_trading_mode=PaperTradingMode.LOCAL,
        )
        app.add_strategy(FireOnceStrategy)
        mock_get_ohlcv.return_value = None
        app.run(number_of_iterations=1)

        orders = app.container.order_service().get_all()
        self.assertEqual(1, len(orders))
        self.assertEqual("OPEN", orders[0].status)

        # A bar after the order's updated_at whose Low touches (or
        # goes below) the BUY order's price confirms the fill, exactly
        # like BacktestTradeOrderEvaluator does for backtests.
        bar_time = orders[0].updated_at + timedelta(seconds=1)
        mock_get_ohlcv.return_value = pl.DataFrame({
            "Datetime": [bar_time],
            "Open": [95.0],
            "High": [105.0],
            "Low": [90.0],
            "Close": [95.0],
            "Volume": [1000.0],
        })

        app.run(number_of_iterations=1)

        orders = app.container.order_service().get_all()
        self.assertEqual(1, len(orders))
        self.assertEqual("CLOSED", orders[0].status)
        self.assertEqual(orders[0].amount, orders[0].filled)

    def test_broker_paper_trading_raises_when_sandbox_unsupported(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        with patch.object(
            CCXTOrderExecutor, "supports_sandbox_mode", return_value=False
        ), patch.object(
            CCXTPortfolioProvider,
            "supports_sandbox_mode",
            return_value=False,
        ):
            with self.assertRaisesRegex(
                OperationalException, "does not advertise a"
            ):
                app.add_market(
                    market="BINANCE",
                    trading_symbol="EUR",
                    initial_balance=1000,
                    paper_trading=True,
                    paper_trading_mode=PaperTradingMode.BROKER,
                )

    def test_auto_paper_trading_uses_broker_sandbox_when_supported(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})

        with patch.object(
            CCXTOrderExecutor, "supports_sandbox_mode", return_value=True
        ), patch.object(
            CCXTPortfolioProvider, "supports_sandbox_mode", return_value=True
        ):
            app.add_market(
                market="BINANCE",
                trading_symbol="EUR",
                initial_balance=1000,
                paper_trading=True,
                paper_trading_mode=PaperTradingMode.AUTO,
            )

        executors = app.get_order_executors()
        sandbox_executors = [
            e for e in executors
            if isinstance(e, CCXTOrderExecutor) and e.sandbox
        ]
        self.assertEqual(1, len(sandbox_executors))
        self.assertTrue(sandbox_executors[0].supports_market("BINANCE"))
        self.assertFalse(sandbox_executors[0].supports_market("KRAKEN"))

        providers = app.get_portfolio_providers()
        sandbox_providers = [
            p for p in providers
            if isinstance(p, CCXTPortfolioProvider) and p.sandbox
        ]
        self.assertEqual(1, len(sandbox_providers))

    def test_paper_trading_executor_does_not_shadow_other_markets(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_balance=1000,
            paper_trading=True,
            paper_trading_mode=PaperTradingMode.LOCAL,
        )
        app.add_market(
            market="BINANCE",
            trading_symbol="EUR",
            api_key="x",
            secret_key="y",
        )
        app.initialize_config()
        app.initialize_order_executors()

        order_executor_lookup = app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market("BITVAVO")
        order_executor_lookup.register_order_executor_for_market("BINANCE")

        self.assertIsInstance(
            order_executor_lookup.get_order_executor("BITVAVO"),
            PaperTradingOrderExecutor,
        )
        binance_executor = order_executor_lookup.get_order_executor(
            "BINANCE"
        )
        self.assertIsInstance(binance_executor, CCXTOrderExecutor)
        self.assertFalse(binance_executor.sandbox)
