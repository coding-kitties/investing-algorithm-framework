from datetime import datetime, timezone, timedelta
from typing import Any
import os
import shutil

from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, MarketCredential, PortfolioConfiguration, \
    DataProvider, Schedule, TimeUnit
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.services import \
    BacktestTradeOrderEvaluator
from tests.resources import TestBase


class CustomFeedDataProvider(DataProvider):

    def has_data(self, data_source: DataSource, start_date: datetime = None,
                 end_date: datetime = None) -> bool:
        pass

    def prepare_backtest_data(self, backtest_start_date,
                              backtest_end_date) -> None:
        pass

    def get_data(self, date: datetime = None, start_date: datetime = None,
                 end_date: datetime = None, save: bool = False) -> Any:
        pass

    def get_backtest_data(self, backtest_index_date: datetime,
                          backtest_start_date: datetime = None,
                          backtest_end_date: datetime = None) -> Any:
        pass

    def copy(self, data_source: DataSource) -> "DataProvider":
        pass


class StrategyForTesting(TradingStrategy):
    data_sources = [
        DataSource(
            identifier="DOT/EUR_2h",
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="DOT/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
    ]
    schedule = Schedule.every(2, TimeUnit.HOUR)
    def run_strategy(self, context, data):
        pass

class StrategyForTestingTwo(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="ETH/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="custom_feed_data"
        ),
    ]
    schedule = Schedule.every(4, TimeUnit.HOUR)
    def run_strategy(self, context, data):
        pass


class StrategyForTestingThree(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            warmup_window=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="twitter_data"
        ),
    ]
    schedule = Schedule.every(1, TimeUnit.DAY)
    def run_strategy(self, context, market_data):
        pass


class TestEventloopService(TestBase):
    initialize = False
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_balances = {
        "EUR": 1000
    }
    portfolio_configurations = [
        PortfolioConfiguration(
            market="bitvavo",
            trading_symbol="EUR",
            initial_balance=1000
        )
    ]


    def test_initialize(self):
        self.app.initialize_config()
        self.app.initialize_storage()
        self.app.initialize_services()
        self.app.initialize_portfolios()
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service(),
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
        )
        self.app.add_strategy(
            StrategyForTesting(),
        )
        self.app.add_strategy(
            StrategyForTestingTwo(),
        )
        self.app.add_strategy(
            StrategyForTestingThree(),
        )
        event_loop_service.initialize(
            trade_order_evaluator=BacktestTradeOrderEvaluator(
                trade_service=self.app.container.trade_service(),
                order_service=self.app.container.order_service(),
                trade_stop_loss_service=self.app.container.trade_stop_loss_service(),
                trade_take_profit_service=self.app.container.trade_take_profit_service(),
            ),
            algorithm=self.app.get_algorithm()
        )
        self.assertEqual(len(event_loop_service.next_run_times), 3)
        self.assertEqual(len(event_loop_service.data_sources), 5)

        # Each entry tracks last_run (None until first execution).
        for strategy in event_loop_service.strategies:
            self.assertIn(
                strategy.strategy_id,
                event_loop_service.next_run_times
            )
            self.assertIsNone(
                event_loop_service
                .next_run_times[strategy.strategy_id]["last_run"]
            )

    def test_get_data_sources_for_iteration(self):
        correct_data_sources = [
            DataSource(
                data_type=DataType.OHLCV,
                warmup_window=200,
                symbol="ETH/EUR",
                time_frame="2h",
                market="bitvavo"
            ),
            DataSource(
                data_type=DataType.CUSTOM,
                data_provider_identifier="custom_feed_data"
            ),
            DataSource(
                data_type=DataType.OHLCV,
                warmup_window=200,
                symbol="DOT/EUR",
                time_frame="2h",
                market="bitvavo"
            )
        ]

        data_sources = EventLoopService._get_data_sources_for_iteration(
            [
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="DOT/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.CUSTOM,
                    data_provider_identifier="custom_feed_data"
                ),
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.OHLCV,
                    warmup_window=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.CUSTOM,
                    data_provider_identifier="custom_feed_data"
                ),
            ],
        )

        self.assertEqual(data_sources, set(correct_data_sources))

    def tearDown(self) -> None:
        super().tearDown()

        databases_directory = os.path.join(
            self.resource_directory, "databases"
        )
        backtest_databases_directory = os.path.join(
            self.resource_directory, "backtest_databases"
        )

        if os.path.exists(databases_directory):
            shutil.rmtree(databases_directory, ignore_errors=True)

        if os.path.exists(backtest_databases_directory):
            shutil.rmtree(backtest_databases_directory, ignore_errors=True)
