# import os
# import time
# import pandas as pd
# from datetime import datetime, timedelta, timezone
# from unittest import TestCase
# from typing import Dict, Any, List
#
# from pyindicators import ema, crossover, crossunder, macd
#
# from investing_algorithm_framework import TradingStrategy, DataSource, \
#     TimeUnit, DataType
# from investing_algorithm_framework import create_app, BacktestDateRange, \
#     Algorithm, RESOURCE_DIRECTORY, SnapshotInterval
#
#
# class MovingAverageCrossoverVectorizedBacktest(TradingStrategy):
#     """
#     A trading strategy that implements a moving average crossover
#     using vectorized backtesting.
#     """
#     time_unit = TimeUnit.HOUR
#     interval = 2
#
#     def __init__(
#         self,
#         macd_time_frame,
#         macd_short_period,
#         macd_long_period,
#         macd_signal_period,
#         data_sources: List[DataSource],
#         ema_time_frame,
#         ema_short_period,
#         ema_long_period
#     ):
#         super().__init__()
#         self.data_sources = data_sources
#         self.macd_time_frame = macd_time_frame
#         self.macd_short_period = macd_short_period
#         self.macd_long_period = macd_long_period
#         self.macd_signal_period = macd_signal_period
#         self.ema_time_frame = ema_time_frame
#         self.ema_short_period = ema_short_period
#         self.ema_long_period = ema_long_period
#         self.data_sources = data_sources
#
#     def buy_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
#         """
#         Generate buy signals when:
#         - EMA short crosses above EMA long (on ema_time_frame)
#         - MACD histogram is positive (on macd_time_frame)
#
#         Args:
#             data (Dict[DataSource, Any]): Dictionary of OHLCV DataFrames.
#
#         Returns:
#             pd.Series: Series of buy signals (True/False).
#         """
#
#         # 1. Get OHLCV data for EMA and MACD based on respective timeframes
#         macd_df = data["macd_data"].copy()
#         ema_df = data["ema_data"].copy()
#
#         # 2. Compute EMA short and long on EMA timeframe
#         ema_df = ema(ema_df, period=self.ema_short_period, source_column="Close", result_column=f"ema_{self.ema_short_period}")
#         ema_df = ema(ema_df, period=self.ema_long_period, source_column="Close", result_column=f"ema_{self.ema_long_period}")
#
#         # Detect crossover (short EMA crosses above long EMA)
#         ema_df = crossover(
#             ema_df,
#             first_column=f"ema_{self.ema_short_period}",
#             second_column=f"ema_{self.ema_long_period}",
#             result_column="ema_crossover"
#         )
#
#         # 3. Compute MACD line, signal line, histogram
#         macd_df = macd(
#             macd_df,
#             short_period=self.macd_short_period,
#             long_period=self.macd_long_period,
#             signal_period=self.macd_signal_period,
#             source_column="Close",
#         )
#
#         # 4. Combine signals (ensure matching index!)
#         combined_index = ema_df.index.intersection(macd_df.index)
#         buy_signal = (
#             ema_df.loc[combined_index, "ema_crossover"] &
#             (macd_df.loc[combined_index, "macd_histogram"] > 0)
#         )
#
#         return buy_signal.fillna(False)
#
#     def sell_signal_vectorized(self, data: Dict[str, Any]) -> pd.Series:
#         """
#         Generate sell signals based on the moving average crossover.
#
#         Args:
#             data (pd.DataFrame): DataFrame containing OHLCV data.
#
#         Returns:
#             pd.Series: Series of sell signals (1 for sell, 0 for no action).
#         """
#
#         # 1. Get OHLCV data for EMA and MACD
#         macd_df = data["macd_data"].copy()
#         ema_df = data["ema_data"].copy()
#
#         # 2. Compute EMA short and long on EMA timeframe
#         ema_df = ema(ema_df, period=self.ema_short_period,
#                      source_column="Close",
#                      result_column=f"ema_{self.ema_short_period}")
#         ema_df = ema(ema_df, period=self.ema_long_period,
#                      source_column="Close",
#                      result_column=f"ema_{self.ema_long_period}")
#
#         # Detect crossover (short EMA crosses above long EMA)
#         ema_df = crossunder(
#             ema_df,
#             first_column=f"ema_{self.ema_short_period}",
#             second_column=f"ema_{self.ema_long_period}",
#             result_column="ema_crossunder"
#         )
#
#         # 3. Compute MACD line, signal line, histogram
#         macd_df = macd(
#             macd_df,
#             short_period=self.macd_short_period,
#             long_period=self.macd_long_period,
#             signal_period=self.macd_signal_period,
#             source_column="Close",
#         )
#
#         # 4. Combine: only trigger if both EMA crossunder and MACD bearish
#         combined_index = ema_df.index.intersection(macd_df.index)
#         sell_signal = (
#                 ema_df.loc[combined_index, "ema_crossunder"] &
#                 (macd_df.loc[combined_index, "macd_histogram"] < 0)
#         )
#
#         return sell_signal.fillna(False)
#
#
# class Test(TestCase):
#
#     def test_run(self):
#         """
#         """
#         start_time = time.time()
#         # RESOURCE_DIRECTORY should always point to the parent directory/resources
#         # Resource directory should point to /tests/resources
#         import os
#
#         # Resource directory is two levels up from the current file
#         resource_directory = os.path.join(
#             os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources'
#         )
#         config = {RESOURCE_DIRECTORY: resource_directory}
#         app = create_app(name="GoldenCrossStrategy", config=config)
#         app.add_market(
#             market="BITVAVO", trading_symbol="EUR", initial_balance=400
#         )
#         end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
#         start_date = end_date - timedelta(days=400)
#         date_range = BacktestDateRange(
#             start_date=start_date, end_date=end_date
#         )
#         backtest = app.run_vector_backtest(
#             initial_amount=1000,
#             backtest_date_range=date_range,
#             strategy=MovingAverageCrossoverVectorizedBacktest(
#                 ema_time_frame="1d",
#                 ema_short_period=50,
#                 ema_long_period=200,
#                 macd_time_frame="2h",
#                 macd_short_period=12,
#                 macd_long_period=26,
#                 macd_signal_period=9,
#                 data_sources=[
#                     DataSource(
#                         identifier="macd_data",
#                         data_type=DataType.OHLCV,
#                         time_frame="2h",
#                         market="BITVAVO",
#                         symbol="BTC/EUR",
#                         pandas=True
#                     ),
#                     DataSource(
#                         identifier="ema_data",
#                         data_type=DataType.OHLCV,
#                         time_frame="2h",
#                         market="BITVAVO",
#                         symbol="ETH/EUR",
#                         pandas=True
#                     ),
#                 ]
#             ),
#             snapshot_interval=SnapshotInterval.DAILY
#         )
#         end_time = time.time()
#         elapsed_time = end_time - start_time
#         print(f"Test completed in {elapsed_time:.2f} seconds")
#
#         # Check that all the required attributes of the backtest results are present
#         backtest_results = backtest.backtest_results
#         backtest_metrics = backtest.backtest_metrics
#         self.assertIsNotNone(backtest_metrics.growth)
#         self.assertIsNotNone(backtest_metrics.growth_percentage)
#         self.assertIsNotNone(backtest_results.initial_unallocated)
#         self.assertIsNotNone(backtest_results.trading_symbol)
#         self.assertIsNotNone(backtest_metrics.total_return)
#         self.assertIsNotNone(backtest_metrics.total_return_percentage)
#         self.assertIsNotNone(backtest_results.get_portfolio_snapshots())
#
