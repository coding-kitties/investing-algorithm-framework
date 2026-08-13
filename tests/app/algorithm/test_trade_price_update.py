import os
import shutil
import unittest
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    MarketCredential, DataSource, INDEX_DATETIME, DataType, \
    CSVOHLCVDataProvider, BacktestDateRange, Schedule
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from investing_algorithm_framework.services import \
    DefaultTradeOrderEvaluator
from tests.resources import random_string, \
    PortfolioProviderTest, OrderExecutorTest


class StrategyOne(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    data_sources = [
        DataSource(
            symbol="BTC/EUR",
            market="BINANCE",
            time_frame="2h",
            data_type=DataType.OHLCV,
            warmup_window=200
        )
    ]

    def apply_strategy(self, context, data):
        pass


class Test(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def tearDown(self) -> None:
        super().tearDown()
        teardown_sqlalchemy()
        database_dir = os.path.join(self.resource_dir, "databases")
        if os.path.exists(database_dir):
            shutil.rmtree(database_dir, ignore_errors=True)

    def test_trade_recent_price_update(self):
        backtest_date_range = BacktestDateRange(
            start_date=datetime(
                2023, 11, 2, 8, 0, tzinfo=timezone.utc
            ),
            end_date=datetime(
                2023, 12, 2, 0, 0, tzinfo=timezone.utc
            ),
        )
        app = create_app(
            config={
                RESOURCE_DIRECTORY: self.resource_dir,
                INDEX_DATETIME:
                    backtest_date_range.start_date
            }
        )
        app.add_data_provider(
            CSVOHLCVDataProvider(
                market="BINANCE",
                symbol="BTC/EUR",
                time_frame="2h",
                warmup_window=200,
                storage_path=os.path.join(
                    self.resource_dir,
                    "test_data", "ohlcv",
                    "OHLCV_BTC-EUR_BINANCE"
                    "_2h_2023-08-07-07-59"
                    "_2023-12-02-00-00.csv"
                ),
            ),
            priority=1
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.container \
            .portfolio_configuration_service().clear()
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE",
                trading_symbol="EUR",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key=random_string(10),
                secret_key=random_string(10)
            )
        )
        app.add_strategy(StrategyOne)
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        app.initialize_portfolios()
        algorithm = app.get_algorithm()
        app.initialize_data_sources_backtest(
            algorithm.data_sources, backtest_date_range
        )
        app.context.create_limit_order(
            target_symbol="btc",
            amount=1,
            price=20,
            order_side="BUY"
        )
        order_service = app.container.order_service()
        order_service.check_pending_orders()

        # `app.run()` always re-initializes data sources via the live
        # (non-backtest) path, which would discard the backtest
        # registration above — drive the event loop directly instead,
        # reusing the already-initialized backtest data providers.
        trade_order_evaluator = DefaultTradeOrderEvaluator(
            trade_service=app.container.trade_service(),
            order_service=order_service,
            trade_stop_loss_service=app.container.trade_stop_loss_service(),
            trade_take_profit_service=app.container
            .trade_take_profit_service(),
            configuration_service=app.container.configuration_service(),
            blotter=app.get_blotter(),
            context=app.context,
        )
        event_loop_service = EventLoopService(
            configuration_service=app.container.configuration_service(),
            portfolio_snapshot_service=app.container
            .portfolio_snapshot_service(),
            context=app.context,
            order_service=order_service,
            portfolio_service=app.container.portfolio_service(),
            data_provider_service=app.container.data_provider_service(),
            trade_service=app.container.trade_service(),
        )
        event_loop_service.initialize(
            algorithm, trade_order_evaluator=trade_order_evaluator
        )
        event_loop_service.start(number_of_iterations=1)

        trade = app.context.get_trades()[0]
        self.assertIsNotNone(trade)
        self.assertIsNotNone(trade.last_reported_price)
