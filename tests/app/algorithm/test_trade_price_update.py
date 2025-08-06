# import os
# from datetime import datetime, timezone
# from unittest import TestCase
#
# from investing_algorithm_framework import create_app, TradingStrategy, \
#     TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
#     Algorithm, MarketCredential, DataSource, INDEX_DATETIME, DataType, \
#     CSVOHLCVDataProvider, BacktestDateRange
# from tests.resources import random_string, \
#     PortfolioProviderTest, OrderExecutorTest
#
# class StrategyOne(TradingStrategy):
#     time_unit = TimeUnit.SECOND
#     interval = 2
#     data_sources = [
#         DataSource(symbol="BTC/EUR", market="BINANCE", time_frame="2h", data_type=DataType.OHLCV, window_size=200)
#     ]
#
#     def apply_strategy(self, context, data):
#         pass
#
# class Test(TestCase):
#
#     def setUp(self) -> None:
#         self.resource_dir = os.path.abspath(
#             os.path.join(
#                 os.path.join(
#                     os.path.join(
#                         os.path.join(
#                             os.path.realpath(__file__),
#                             os.pardir
#                         ),
#                         os.pardir
#                     ),
#                     os.pardir
#                 ),
#                 "resources"
#             )
#         )
#
#     def tearDown(self) -> None:
#         super().tearDown()
#         # Delete the resources database directory
#
#         database_dir = os.path.join(self.resource_dir, "databases")
#
#         if os.path.exists(database_dir):
#             for root, dirs, files in os.walk(database_dir, topdown=False):
#                 for name in files:
#                     os.remove(os.path.join(root, name))
#                 for name in dirs:
#                     os.rmdir(os.path.join(root, name))
#
#     def test_trade_recent_price_update(self):
#         backtest_date_range = BacktestDateRange(
#             start_date=datetime(2023, 11, 2, 8, 0, tzinfo=timezone.utc),
#             end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc),
#         )
#         app = create_app(
#             config={
#                 RESOURCE_DIRECTORY: self.resource_dir,
#                 INDEX_DATETIME: backtest_date_range.start_date
#             }
#         )
#         app.add_data_provider(
#             CSVOHLCVDataProvider(
#                 market="BINANCE",
#                 symbol="BTC/EUR",
#                 time_frame="2h",
#                 window_size=200,
#                 storage_path=os.path.join(
#                     self.resource_dir,
#                     "market_data_sources_for_testing",
#                     "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
#                 ),
#             ),
#             priority=1
#         )
#         app.add_portfolio_provider(PortfolioProviderTest)
#         app.add_order_executor(OrderExecutorTest)
#         app.container.portfolio_configuration_service().clear()
#         app.add_portfolio_configuration(
#             PortfolioConfiguration(
#                 market="BINANCE",
#                 trading_symbol="EUR",
#             )
#         )
#         app.add_market_credential(
#             MarketCredential(
#                 market="BINANCE",
#                 api_key=random_string(10),
#                 secret_key=random_string(10)
#             )
#         )
#         app.add_strategy(StrategyOne)
#         app.initialize_config()
#         app.initialize_storage()
#         app.initialize_services()
#         app.initialize_portfolios()
#         algorithm = app.get_algorithm()
#         app.initialize_data_sources_backtest(algorithm.data_sources, backtest_date_range)
#         app.context.create_limit_order(
#             target_symbol="btc",
#             amount=1,
#             price=20,
#             order_side="BUY"
#         )
#         order_service = app.container.order_service()
#         order_service.check_pending_orders()
#         app.run(number_of_iterations=1)
#         trade = app.context.get_trades()[0]
#         self.assertIsNotNone(trade)
#         self.assertIsNotNone(trade.last_reported_price)
