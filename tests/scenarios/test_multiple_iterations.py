# import os
# import time
# from datetime import datetime, timedelta, timezone
# from pathlib import Path
# from typing import Dict, Any
# from unittest import TestCase
#
# import pandas as pd
#
# from investing_algorithm_framework import TradingStrategy, DataSource, \
#     TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
#     RESOURCE_DIRECTORY, SnapshotInterval, StopLossRule, TakeProfitRule, \
#     ExitType, CSVOHLCVDataProvider, TradeStatus
#
#
# class TrailingTakeProfitsStopLossesStrategy(TradingStrategy):
#     time_unit = TimeUnit.HOUR
#     interval = 2
#     symbols = ["BTC"]
#     data_sources = [
#         DataSource(
#             symbol="BTC/EUR",
#             data_type=DataType.OHLCV,
#             time_frame="2h",
#             window_size=200,
#             market="BITVAVO",
#             identifier="BTC_EUR_OHLCV",
#             pandas=True
#         ),
#     ]
#     position_sizes = [
#         PositionSize(
#             symbol="BTC",
#             percentage_of_portfolio=20.0
#         ),
#         PositionSize(
#             symbol="ETH",
#             percentage_of_portfolio=20.0
#         )
#     ]
#     take_profit_rules = [
#         TakeProfitRule(
#             symbol="BTC",
#             percentage_threshold=10.0,
#             exit_type=ExitType.FIXED,
#             sell_percentage=50
#         ),
#     ]
#     # stop_loss_rules = [
#     #     StopLossRule(
#     #         symbol="BTC",
#     #         percentage_threshold=10,
#     #         exit_type=ExitType.TRAILING,
#     #         sell_percentage=50
#     #     )
#     # ]
#
#     def generate_sell_signals(
#         self, data: Dict[str, Any]
#     ) -> Dict[str, pd.Series]:
#         signals = {}
#
#         for symbol in self.symbols:
#             df = data["BTC_EUR_OHLCV"]
#             signals[symbol] = pd.Series(
#                 [False] * len(df), index=df.index
#             )
#
#         return signals
#
#     def generate_buy_signals(
#         self, data: Dict[str, Any]
#     ) -> Dict[str, pd.Series]:
#         signals = {}
#
#         for symbol in self.symbols:
#             df = data["BTC_EUR_OHLCV"]
#             last_row = df.iloc[-1]
#             last_price = last_row['Close']
#
#             if last_price > 30330:
#                 # Max price is 33701 where want to set the take
#                 # profit at 10% fixex
#                 signals[symbol] = pd.Series(
#                     [True] * len(df), index=df.index
#                 )
#             else:
#                 signals[symbol] = pd.Series(
#                     [False] * len(df), index=df.index
#                 )
#
#         return signals
#
# class Test(TestCase):
#
#     def test_run_trailing_stop_losses_take_profits(self):
#         """
#         """
#         start_time = time.time()
#         # RESOURCE_DIRECTORY should always point to the parent directory/resources
#         # Resource directory should point to /tests/resources
#         resource_directory = str(Path(__file__).parent.parent.parent / 'resources')
#         config = {RESOURCE_DIRECTORY: resource_directory}
#         app = create_app(name="GoldenCrossStrategy", config=config)
#         app.add_market(
#             market="BITVAVO", trading_symbol="EUR", initial_balance=400
#         )
#         start_date = datetime(2020, 12, 29, tzinfo=timezone.utc)
#         end_date = datetime(2021, 1, 31, tzinfo=timezone.utc)
#         strategy = TrailingTakeProfitsStopLossesStrategy()
#         # Create CSV OHLCV data provider for csv file in resources/data/BITVAVO/BTC-EUR/2h/ohlcv.csv
#         # This csv file has a 10% price increase followed by a 10% price decrease to trigger
#         # both the take profit and stop loss rules
#         csv_file_path = str(Path(__file__).parent.parent / 'resources' / 'test_data' / 'ohlcv' / 'OHLCV_BTC-EUR_BITVAVO_2h_2020-12-15-07-00_2021-01-31-23-00.csv')
#         csv_data_provider = CSVOHLCVDataProvider(
#             storage_path=csv_file_path,
#             symbol="BTC/EUR",
#             time_frame="2h",
#             market="BITVAVO",
#             window_size=200
#         )
#         app.add_data_provider(
#             data_provider=csv_data_provider, priority=1
#         )
#         backtest_date_range = BacktestDateRange(
#             start_date=start_date, end_date=end_date
#         )
#         backtest = app.run_backtest(
#             strategy=strategy,
#             backtest_date_range=BacktestDateRange(
#                 start_date=start_date, end_date=end_date
#             )
#         )
#         # Check that 2 orders are created: one buy and one sell
#         run = backtest.get_backtest_run(backtest_date_range)
#         orders = run.get_orders()
#
#         # There should be 2 orders: 1 buy and 1 sell
#         self.assertEqual(2, len(orders))
#         self.assertEqual(1, len(run.get_trades()))
#
#         # Check that the trade was triggered by a take profit
#         trade = run.get_trades(target_symbol="BTC")[0]
#
#         # The trade should still be open
#         self.assertTrue(TradeStatus.OPEN.equals(trade.status))
