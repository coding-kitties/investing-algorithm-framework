from datetime import datetime, timezone, timedelta

from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, MarketCredential, PortfolioConfiguration, Order, Trade, \
    CCXTOHLCVDataProvider, BacktestDateRange, DataProvider, \
    BACKTESTING_INDEX_DATETIME, OrderStatus
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.domain import ENVIRONMENT, Environment, \
    BACKTESTING_START_DATE, BACKTESTING_LAST_SNAPSHOT_DATETIME, \
    SNAPSHOT_INTERVAL, SnapshotInterval
from investing_algorithm_framework.infrastructure import BacktestOrderExecutor
from investing_algorithm_framework.services import DataProviderService, \
    BacktestTradeOrderEvaluator
from tests.resources import TestBase


class CustomFeedDataProvider(DataProvider):

    def has_data(
        self, data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> bool:
        pass

    def get_data(self, data_source: DataSource, date: datetime = None,
                 start_date: datetime = None, end_date: datetime = None,
                 save: bool = False):
        pass

    def prepare_backtest_data(self, data_source: DataSource,
                              backtest_start_date, backtest_end_date) -> None:
        pass

    def get_backtest_data(self, data_source: DataSource,
                          backtest_index_date: datetime,
                          backtest_start_date: datetime = None,
                          backtest_end_date: datetime = None) -> None:
        pass


class StrategyForTesting(TradingStrategy):
    data_sources = [
        DataSource(
            identifier="DOT/EUR_2h",
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="DOT/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
    ]
    time_unit = "hour"
    interval = 2

    def run_strategy(self, context, market_data):
        pass

class StrategyForTestingTwo(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="ETH/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="custom_feed_data"
        ),
    ]
    time_unit = "hour"
    interval = 4

    def run_strategy(self, context, market_data):
        pass


class StrategyForTestingThree(TradingStrategy):
    data_sources = [
        DataSource(
            data_type=DataType.OHLCV,
            window_size=200,
            symbol="BTC/EUR",
            time_frame="2h",
            market="bitvavo"
        ),
        DataSource(
            data_type=DataType.CUSTOM,
            data_provider_identifier="twitter_data"
        ),
    ]
    time_unit = "day"
    interval = 1

    def run_strategy(self, context, market_data):
        pass


class TestEventloopService(TestBase):
    initialize = False
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def test_initialize(self):
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=self.app.container.data_provider_service()
        )
        event_loop_service.strategies = [
            StrategyForTesting(),
            StrategyForTestingTwo(),
            StrategyForTestingThree()
        ]
        event_loop_service.initialize()
        self.assertEqual(len(event_loop_service.next_run_times), 3)
        self.assertEqual(len(event_loop_service.data_sources), 5)

        # Each next run time should be set to the current datatime
        # because no runs have been executed yet
        for strategy in event_loop_service.strategies:
            self.assertIn(
                strategy.strategy_id,
                event_loop_service.next_run_times
            )
            self.assertAlmostEqual(
                event_loop_service\
                    .next_run_times[strategy.strategy_id]["next_run"],
                datetime.now(tz=timezone.utc),
                delta=timedelta(seconds=10)
            )

    def test_get_data_sources_for_iteration(self):
        correct_data_sources = [
            DataSource(
                data_type=DataType.OHLCV,
                window_size=200,
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
                window_size=200,
                symbol="DOT/EUR",
                time_frame="2h",
                market="bitvavo"
            ),
            DataSource(
                data_type=DataType.OHLCV,
                symbol="BTC/EUR",
            ),
            DataSource(
                data_type=DataType.OHLCV,
                symbol="SOL/EUR",
            ),
            DataSource(
                data_type=DataType.OHLCV,
                symbol="XRP/EUR",
            ),
        ]

        data_sources = EventLoopService._get_data_sources_for_iteration(
            [
                DataSource(
                    data_type=DataType.OHLCV,
                    window_size=200,
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
                    window_size=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.OHLCV,
                    window_size=200,
                    symbol="ETH/EUR",
                    time_frame="2h",
                    market="bitvavo"
                ),
                DataSource(
                    data_type=DataType.CUSTOM,
                    data_provider_identifier="custom_feed_data"
                ),
            ],
            [
                Order(
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    amount=1.0,
                    order_side="buy",
                    order_type="limit",
                    price=100.0,
                    external_id="order_123",
                ),
                Order(
                    target_symbol="XRP",
                    trading_symbol="EUR",
                    amount=2.0,
                    order_side="sell",
                    order_type="limit",
                    price=200.0,
                    external_id="order_456",
                ),
                Order(
                    target_symbol="DOT",
                    trading_symbol="EUR",
                    amount=3.0,
                    order_side="buy",
                    order_type="limit",
                    price=50.0,
                    external_id="order_789",
                )
            ],
            [
                Trade(
                    id=1,
                    orders=[],
                    opened_at=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
                    closed_at=None,
                    available_amount=1.0,
                    filled_amount=1.0,
                    remaining=0.0,
                    cost=10,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    amount=1.0,
                    open_price=100.0,
                    net_gain=10.0,
                    status="closed"
                ),
                Trade(
                    id=1,
                    orders=[],
                    opened_at=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
                    closed_at=None,
                    available_amount=1.0,
                    filled_amount=1.0,
                    remaining=0.0,
                    cost=10,
                    target_symbol="SOL",
                    trading_symbol="EUR",
                    amount=1.0,
                    open_price=100.0,
                    net_gain=10.0,
                    status="closed"
                )
            ]
        )

        self.assertEqual(data_sources, set(correct_data_sources))

    def test_backtest_loop(self):
        data_provider_service = DataProviderService(
            configuration_service=self.app.container.configuration_service(),
            market_credential_service=self.app.container\
                .market_credential_service()
        )
        data_provider_service.add_data_provider(
            CCXTOHLCVDataProvider()
        )

        strategy = StrategyForTesting()
        data_sources = strategy.data_sources
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )

        # Register data providers for data sources
        data_provider_service.index_backtest_data_providers(
            strategy.data_sources,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                data_source,
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

        # There should be a single backtest data provider registered
        self.assertEqual(
            len(data_provider_service.data_provider_index), 2
        )

        # Should be all CCXTOHLCVDataProvider
        for datasource in data_sources:
            data_provider = data_provider_service.find_data_provider(datasource)
            self.assertIsNotNone(data_provider)
            self.assertTrue(
                isinstance(data_provider, CCXTOHLCVDataProvider)
            )

        backtest_trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
        )
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=data_provider_service,
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
            trade_order_evaluator=backtest_trade_order_evaluator
        )
        event_loop_service.strategies = [StrategyForTesting()]
        event_loop_service.initialize()
        event_loop_service.start(number_of_iterations=1)
        history = event_loop_service.history

        # StrategyOne should have run once
        self.assertEqual(
            len(history[strategy.strategy_id]["runs"]), 1
        )

    def test_backtest_loop_with_executed_orders(self):
        """

        """
        # Set the app in backtest mode
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 8, 28, 8, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc)
        )
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(BACKTESTING_INDEX_DATETIME,
                                        backtest_date_range.start_date)
        configuration_service.add_value(ENVIRONMENT,
                                        Environment.BACKTEST.value)
        configuration_service.add_value(BACKTESTING_START_DATE,
                                        backtest_date_range.start_date)

        self.app.add_order_executor(BacktestOrderExecutor())
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.initialize()
        order_service = self.app.container.order_service()
        order_service.create(
            {
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": 0.000002,
                "order_side": "buy",
                "order_type": "limit",
                "price": 1000000,
                "portfolio_id": 1
            }
        )

        data_provider_service = DataProviderService(
            configuration_service=self.app.container.configuration_service(),
            market_credential_service=self.app.container\
                .market_credential_service()
        )
        data_provider_service.add_data_provider(
            CCXTOHLCVDataProvider()
        )
        strategy = StrategyForTesting()
        data_sources = strategy.data_sources
        # Register data providers for data sources
        data_provider_service.index_backtest_data_providers(
            strategy.data_sources,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                data_source,
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

        # There should be a single backtest data provider registered
        self.assertEqual(
            len(data_provider_service.data_provider_index), 2
        )

        # Should be all CCXTOHLCVDataProvider
        for datasource in data_sources:
            data_provider = data_provider_service.find_data_provider(datasource)
            self.assertIsNotNone(data_provider)
            self.assertTrue(
                isinstance(data_provider, CCXTOHLCVDataProvider)
            )

        backtest_trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
        )
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=data_provider_service,
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
            trade_order_evaluator=backtest_trade_order_evaluator
        )
        event_loop_service.strategies = [StrategyForTesting()]
        event_loop_service.initialize()
        event_loop_service.start(number_of_iterations=1)
        history = event_loop_service.history

        # StrategyOne should have run once
        self.assertEqual(
            len(history[strategy.strategy_id]["runs"]), 1
        )
        # Check if the order was executed
        orders = order_service.get_all()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, OrderStatus.CLOSED.value)
        self.assertNotEqual(orders[0].filled, 0)
        self.assertEqual(orders[0].remaining, 0.0)

    def test_event_loop_with_schedule(self):
        """

        """
        # Set the app in backtest mode
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, 0, 0, tzinfo=timezone.utc)
        )
        number_of_days = (backtest_date_range.end_date - backtest_date_range.start_date).days
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(BACKTESTING_INDEX_DATETIME,
                                        backtest_date_range.start_date)
        configuration_service.add_value(ENVIRONMENT,
                                        Environment.BACKTEST.value)
        configuration_service.add_value(BACKTESTING_START_DATE,
                                        backtest_date_range.start_date)
        configuration_service.add_value(BACKTESTING_LAST_SNAPSHOT_DATETIME, backtest_date_range.start_date)
        configuration_service.add_value(SNAPSHOT_INTERVAL, SnapshotInterval.DAILY.value)
        strategy = StrategyForTesting()
        backtest_service = self.app.container.backtest_service()
        schedule = backtest_service.generate_schedule(
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date,
            strategies=[strategy],
            tasks=[]
        )
        self.app.add_order_executor(BacktestOrderExecutor())
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.initialize()


        data_provider_service = DataProviderService(
            configuration_service=self.app.container.configuration_service(),
            market_credential_service=self.app.container\
                .market_credential_service()
        )
        data_provider_service.add_data_provider(
            CCXTOHLCVDataProvider()
        )
        data_sources = strategy.data_sources
        # Register data providers for data sources
        data_provider_service.index_backtest_data_providers(
            strategy.data_sources,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                data_source,
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

        # There should be a single backtest data provider registered
        self.assertEqual(
            len(data_provider_service.data_provider_index), 2
        )

        # Should be all CCXTOHLCVDataProvider
        for datasource in data_sources:
            data_provider = data_provider_service.find_data_provider(datasource)
            self.assertIsNotNone(data_provider)
            self.assertTrue(
                isinstance(data_provider, CCXTOHLCVDataProvider)
            )

        backtest_trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
        )
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=data_provider_service,
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
            trade_order_evaluator=backtest_trade_order_evaluator
        )
        event_loop_service.strategies = [StrategyForTesting()]
        event_loop_service.initialize()
        event_loop_service.start(schedule=schedule, show_progress=True)

        # Check that for every day a snapshot was created
        portfolio_snapshot_service = self.app.container.portfolio_snapshot_service()
        self.assertEqual(
            len(portfolio_snapshot_service.get_all()), number_of_days
        )
        history = event_loop_service.history

        # StrategyOne should have run 8749 times
        self.assertEqual(
            len(history[strategy.strategy_id]["runs"]), 8749
        )

    def test_backtest_loop_with_strategy_iteration_snapshotting(self):
        """

        """
        # Set the app in backtest mode
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, 0, 0, tzinfo=timezone.utc)
        )
        number_of_days = (backtest_date_range.end_date - backtest_date_range.start_date).days
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(BACKTESTING_INDEX_DATETIME,
                                        backtest_date_range.start_date)
        configuration_service.add_value(ENVIRONMENT,
                                        Environment.BACKTEST.value)
        configuration_service.add_value(BACKTESTING_START_DATE,
                                        backtest_date_range.start_date)
        configuration_service.add_value(BACKTESTING_LAST_SNAPSHOT_DATETIME, backtest_date_range.start_date)
        configuration_service.add_value(SNAPSHOT_INTERVAL, SnapshotInterval.STRATEGY_ITERATION.value)
        strategy = StrategyForTesting()
        backtest_service = self.app.container.backtest_service()
        schedule = backtest_service.generate_schedule(
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date,
            strategies=[strategy],
            tasks=[]
        )
        self.app.add_order_executor(BacktestOrderExecutor())
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.initialize()
        data_provider_service = DataProviderService(
            configuration_service=self.app.container.configuration_service(),
            market_credential_service=self.app.container\
                .market_credential_service()
        )
        data_provider_service.add_data_provider(
            CCXTOHLCVDataProvider()
        )
        data_sources = strategy.data_sources
        # Register data providers for data sources
        data_provider_service.index_backtest_data_providers(
            strategy.data_sources,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                data_source,
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

        # There should be a single backtest data provider registered
        self.assertEqual(
            len(data_provider_service.data_provider_index), 2
        )

        # Should be all CCXTOHLCVDataProvider
        for datasource in data_sources:
            data_provider = data_provider_service.find_data_provider(datasource)
            self.assertIsNotNone(data_provider)
            self.assertTrue(
                isinstance(data_provider, CCXTOHLCVDataProvider)
            )

        backtest_trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
        )
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=data_provider_service,
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
            trade_order_evaluator=backtest_trade_order_evaluator
        )
        event_loop_service.strategies = [StrategyForTesting()]
        event_loop_service.initialize()
        event_loop_service.start(schedule=schedule, show_progress=True)

        # Check that for every day a snapshot was created
        portfolio_snapshot_service = self.app.container.portfolio_snapshot_service()
        self.assertEqual(
            len(portfolio_snapshot_service.get_all()), 8749
        )
        history = event_loop_service.history
        # StrategyOne should have run 8749 times
        self.assertEqual(
            len(history[strategy.strategy_id]["runs"]), 8749
        )

    def test_schedule_with_daily_iteration_snapshotting(self):
        """

        """
        # Set the app in backtest mode
        # Set the app in backtest mode
        backtest_date_range = BacktestDateRange(
            start_date=datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, 0, 0, tzinfo=timezone.utc)
        )
        number_of_days = (
                    backtest_date_range.end_date - backtest_date_range.start_date).days
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(BACKTESTING_INDEX_DATETIME,
                                        backtest_date_range.start_date)
        configuration_service.add_value(ENVIRONMENT,
                                        Environment.BACKTEST.value)
        configuration_service.add_value(BACKTESTING_START_DATE,
                                        backtest_date_range.start_date)
        configuration_service.add_value(BACKTESTING_LAST_SNAPSHOT_DATETIME,
                                        backtest_date_range.start_date)
        configuration_service.add_value(SNAPSHOT_INTERVAL,
                                        SnapshotInterval.STRATEGY_ITERATION.value)
        strategy = StrategyForTesting()
        backtest_service = self.app.container.backtest_service()
        schedule = backtest_service.generate_schedule(
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date,
            strategies=[strategy],
            tasks=[]
        )
        self.app.add_order_executor(BacktestOrderExecutor())
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.initialize()
        data_provider_service = DataProviderService(
            configuration_service=self.app.container.configuration_service(),
            market_credential_service=self.app.container \
                .market_credential_service()
        )
        data_provider_service.add_data_provider(
            CCXTOHLCVDataProvider()
        )
        data_sources = strategy.data_sources
        # Register data providers for data sources
        data_provider_service.index_backtest_data_providers(
            strategy.data_sources,
            backtest_date_range.start_date,
            backtest_date_range.end_date
        )

        # Prepare the backtest data for each data provider
        for data_source, data_provider in data_provider_service.data_provider_index.get_all():
            data_provider.prepare_backtest_data(
                data_source,
                backtest_start_date=backtest_date_range.start_date,
                backtest_end_date=backtest_date_range.end_date
            )

        # There should be a single backtest data provider registered
        self.assertEqual(
            len(data_provider_service.data_provider_index), 2
        )

        # Should be all CCXTOHLCVDataProvider
        for datasource in data_sources:
            data_provider = data_provider_service.find_data_provider(
                datasource)
            self.assertIsNotNone(data_provider)
            self.assertTrue(
                isinstance(data_provider, CCXTOHLCVDataProvider)
            )

        backtest_trade_order_evaluator = BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
        )
        event_loop_service = EventLoopService(
            order_service=self.app.container.order_service(),
            portfolio_service=self.app.container.portfolio_service(),
            configuration_service=self.app.container.configuration_service(),
            data_provider_service=data_provider_service,
            context=self.app.container.context(),
            trade_service=self.app.container.trade_service(),
            portfolio_snapshot_service=self.app.container.portfolio_snapshot_service(),
            trade_order_evaluator=backtest_trade_order_evaluator
        )
        event_loop_service.strategies = [StrategyForTesting()]
        event_loop_service.initialize()
        event_loop_service.start(schedule=schedule, show_progress=True)

        # Check that for every day a snapshot was created
        portfolio_snapshot_service = self.app.container.portfolio_snapshot_service()
        self.assertEqual(
            len(portfolio_snapshot_service.get_all()), number_of_days
        )
        history = event_loop_service.history
        # StrategyOne should have run 8749 times
        self.assertEqual(
            len(history[strategy.strategy_id]["runs"]), 8749
        )
