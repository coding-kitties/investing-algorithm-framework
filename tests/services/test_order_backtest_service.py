from datetime import datetime
from decimal import Decimal

import polars as pl

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, BACKTESTING_INDEX_DATETIME
from investing_algorithm_framework.services import \
    BacktestMarketDataSourceService, OrderBacktestService
from investing_algorithm_framework.domain import ENVIRONMENT, \
    DATABASE_NAME, DATABASE_DIRECTORY_NAME, Environment, \
    BACKTESTING_START_DATE, BACKTESTING_END_DATE, BACKTESTING_INITIAL_AMOUNT
from tests.resources import TestBase


class TestOrderBacktestService(TestBase):
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000
    }
    initialize = False

    def setUp(self) -> None:
        super(TestOrderBacktestService, self).setUp()
        # Override the MarketDataSourceService service with the backtest
        # market data source service equivalent. Additionally, convert the
        # market data sources to backtest market data sources
        # market_data_sources = self.get_market_data_sources()
        # backtest_market_data_sources = []
        market_data_source_service = \
            self.app.container.market_data_source_service()
        market_data_sources = market_data_source_service\
            .get_market_data_sources()

        backtest_market_data_sources = None

        if market_data_sources is not None:
            backtest_market_data_sources = [
                market_data_source.to_backtest_market_data_source()
                for market_data_source in market_data_sources
            ]

        backtest_market_data_source_service = BacktestMarketDataSourceService(
            market_data_sources=backtest_market_data_sources,
            market_service=self.app.container.market_service(),
            market_credential_service=self.app.container
            .market_credential_service(),
            configuration_service=self.app.container
            .configuration_service(),
        )

        self.app.container.order_service.override(
            OrderBacktestService(
                trade_service=self.app.container.trade_service(),
                order_repository=self.app.container.order_repository(),
                position_repository=self.app.container.position_repository(),
                portfolio_repository=self.app.container.portfolio_repository(),
                portfolio_configuration_service=self.app.container.
                portfolio_configuration_service(),
                portfolio_snapshot_service=self.app.container.
                portfolio_snapshot_service(),
                configuration_service=self.app.container.
                configuration_service(),
                market_data_source_service=backtest_market_data_source_service
            )
        )
        self.app.set_config_with_dict(
            {
                ENVIRONMENT: Environment.BACKTEST.value,
                DATABASE_NAME: "backtest-database.sqlite3",
                DATABASE_DIRECTORY_NAME: "backtest_databases",
                BACKTESTING_START_DATE: datetime(2023, 8, 8),
                BACKTESTING_END_DATE: datetime(2023, 8, 10),
                BACKTESTING_INITIAL_AMOUNT: 1000
            }
        )
        self.app.initialize_config()
        self.app.initialize()

    def test_create_limit_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )

        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

    def test_update_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )

        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        updated_order = order_service.update(
            order.id,
            {
                "status": "CLOSED",
                "filled": 2004.5303357979318,
                "remaining": Decimal('0'),
            }
        )
        self.assertEqual(updated_order.amount, 2004.5303357979318)
        self.assertEqual(updated_order.filled, 2004.5303357979318)
        self.assertEqual(updated_order.remaining, 0)

        position_service = self.app.container.position_service()
        position = position_service.get(order.position_id)
        self.assertEqual(position.amount, 2004.5303357979318)

    def test_create_limit_buy_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

    def test_create_limit_sell_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

        order_service.update(
            order.id,
            {
                "status": "CLOSED",
                "filled": 2004.5303357979318,
                "remaining": Decimal('0'),
            }
        )

        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "SELL",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(2, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("SELL", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())

        # Order is synced so is OPEN
        self.assertEqual("OPEN", order.get_status())

    def test_update_buy_order_with_successful_order(self):
        pass

    def test_update_buy_order_with_successful_order_filled(self):
        pass

    def test_update_sell_order_with_successful_order(self):
        pass

    def test_update_sell_order_with_successful_order_filled(self):
        pass

    def test_update_buy_order_with_failed_order(self):
        pass

    def test_update_sell_order_with_failed_order(self):
        pass

    def test_update_buy_order_with_cancelled_order(self):
        pass

    def test_update_sell_order_with_cancelled_order(self):
        pass

    def test_has_executed_buy_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )

        # Create the buy order
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

        # Check with ohlcv data with a single row that matches the price
        # of the buy order
        ohclv = [
            {
                "Open": 0.24262,
                "High": 0.24262,
                "Low": 0.24262,
                "Close": 0.24262,
                "Volume": 0.24262,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(order, ohlcv_df))

        # Check with ohlcv data with a single row that is lower than the
        # buy order price
        ohclv = [
            {
                "Open": 0.24162,
                "High": 0.24162,
                "Low": 0.24162,
                "Close": 0.24162,
                "Volume": 0.24162,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(order, ohlcv_df))

        # Check with ohlcv data with a single row that is higher than the
        # buy order price
        ohclv = [
            {
                "Open": 0.24362,
                "High": 0.24362,
                "Low": 0.24362,
                "Close": 0.24362,
                "Volume": 0.24362,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertFalse(order_service.has_executed(order, ohlcv_df))

        # Check with multiple rows with all rows having a price higher than
        # the buy order price
        ohclv = [
            {
                "Open": 0.24462,
                "High": 0.24462,
                "Low": 0.24462,
                "Close": 0.24462,
                "Volume": 0.24462,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24300,
                "High": 0.24300,
                "Low": 0.24300,
                "Close": 0.24300,
                "Volume": 0.24300,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertFalse(order_service.has_executed(order, ohlcv_df))

        # Check with multiple rows with the first row have a price lower than
        # the buy order price
        ohclv = [
            {
                "Open": 0.24162,
                "High": 0.24162,
                "Low": 0.24162,
                "Close": 0.24162,
                "Volume": 0.24162,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24200,
                "High": 0.24200,
                "Low": 0.24200,
                "Close": 0.24200,
                "Volume": 0.24200,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24300,
                "High": 0.24300,
                "Low": 0.24300,
                "Close": 0.24300,
                "Volume": 0.24300,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(order, ohlcv_df))

    def test_has_executed_sell_order(self):
        order_service = self.app.container.order_service()
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            BACKTESTING_INDEX_DATETIME,
            datetime.utcnow()
        )

        # Create the buy order
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        self.assertEqual(1, order_service.count())
        self.assertEqual(2004.5303357979318, order.amount)
        self.assertEqual(0, order.get_filled())
        self.assertEqual(2004.5303357979318, order.get_remaining())
        self.assertEqual(0.24262, order.get_price())
        self.assertEqual("ADA", order.get_target_symbol())
        self.assertEqual("EUR", order.get_trading_symbol())
        self.assertEqual("BUY", order.get_order_side())
        self.assertEqual("LIMIT", order.get_order_type())
        self.assertEqual("OPEN", order.get_status())

        # Update the buy order to closed
        order_service.update(
            order.id,
            {
                "status": "CLOSED",
                "filled": 2004.5303357979318,
                "remaining": Decimal('0'),
            }
        )

        # Create the sell order
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004.5303357979318,
                "order_side": "SELL",
                "price": 0.24262,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )

        # Check with ohlcv data with a single row that matches the price
        # of the sell order
        ohclv = [
            {
                "Open": 0.24262,
                "High": 0.24262,
                "Low": 0.24262,
                "Close": 0.24262,
                "Volume": 0.24262,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))

        # Check with ohlcv data with a single row that has higher price then
        # the sell order price
        ohclv = [
            {
                "Open": 0.24362,
                "High": 0.24362,
                "Low": 0.24362,
                "Close": 0.24362,
                "Volume": 0.24362,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))

        # Check with ohlcv data with a single row that has lower price then
        # the sell order price
        ohclv = [
            {
                "Open": 0.24162,
                "High": 0.24162,
                "Low": 0.24162,
                "Close": 0.24162,
                "Volume": 0.24162,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertFalse(order_service.has_executed(sell_order, ohlcv_df))

        # Check with multiple rows with all rows having a price lower than
        # the sell order price
        ohclv = [
            {
                "Open": 0.24162,
                "High": 0.24162,
                "Low": 0.24162,
                "Close": 0.24162,
                "Volume": 0.24162,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24000,
                "High": 0.24000,
                "Low": 0.24000,
                "Close": 0.24000,
                "Volume": 0.24000,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertFalse(order_service.has_executed(sell_order, ohlcv_df))

        # Check with multiple rows with the first row have a price higher than
        # the sell order price
        ohclv = [
            {
                "Open": 0.24300,
                "High": 0.24300,
                "Low": 0.24300,
                "Close": 0.24300,
                "Volume": 0.24300,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24162,
                "High": 0.24162,
                "Low": 0.24162,
                "Close": 0.24162,
                "Volume": 0.24162,
                "Datetime": datetime.now()
            },
            {
                "Open": 0.24000,
                "High": 0.24000,
                "Low": 0.24000,
                "Close": 0.24000,
                "Volume": 0.24000,
                "Datetime": datetime.now()
            }
        ]
        ohlcv_df = pl.DataFrame(ohclv)
        self.assertTrue(order_service.has_executed(sell_order, ohlcv_df))
