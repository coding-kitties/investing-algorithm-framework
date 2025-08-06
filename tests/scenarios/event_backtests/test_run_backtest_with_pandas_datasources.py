# import time
# import os
# from datetime import datetime, timedelta, timezone
# from unittest import TestCase
# import pandas as pd
# import polars as pl
#
# from investing_algorithm_framework import create_app, BacktestDateRange, \
#     Algorithm, RESOURCE_DIRECTORY, PandasOHLCVDataProvider, \
#     convert_polars_to_pandas
# from tests.resources.strategies_for_testing.strategy_v1 import \
#     CrossOverStrategyV1
#
#
# class Test(TestCase):
#
#     def test_run(self):
#         """
#         """
#         start_time = time.time()
#         # RESOURCE_DIRECTORY should point to three directories up from this file
#         # to the resources directory
#         # Get the parent directory of the current file
#
#         resource_directory = os.path.abspath(
#             os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
#         )
#         csv_file_path = f"{resource_directory}/market_data_sources_for_testing" \
#                         "/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv"
#
#         config = {RESOURCE_DIRECTORY: resource_directory}
#         app = create_app(name="GoldenCrossStrategy", config=config)
#         app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)
#         end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
#         start_date = end_date - timedelta(days=99)
#         date_range = BacktestDateRange(
#             start_date=start_date, end_date=end_date
#         )
#         algorithm = Algorithm()
#         strategy = CrossOverStrategyV1()
#
#         # Join the path to the CSV file
#         dataframe = pl.read_csv(csv_file_path)
#         dataframe = convert_polars_to_pandas(dataframe, add_index=False)
#         data_provider = PandasOHLCVDataProvider(
#             data_provider_identifier="BTC/EUR-ohlcv-2h",
#             dataframe=dataframe,
#             market="BITVAVO",
#             symbol="BTC/EUR",
#             time_frame="2h",
#             window_size=200
#         )
#         app.add_data_provider(data_provider, priority=1)
#         algorithm.add_strategy(strategy)
#         backtest_report = app.run_backtest(
#             backtest_date_range=date_range, algorithm=algorithm
#         )
#         self.assertAlmostEqual(
#             backtest_report.backtest_metrics.growth, 5.9, delta=0.5
#         )
#         self.assertAlmostEqual(
#             backtest_report.backtest_metrics.growth_percentage, 0.0149, delta=0.001
#         )
#         self.assertEqual(
#             backtest_report.backtest_results.initial_unallocated, 400
#         )
#         self.assertEqual(
#             backtest_report.backtest_results.trading_symbol, "EUR"
#         )
#         self.assertAlmostEqual(
#             backtest_report.backtest_metrics.total_return, 5.9, delta=0.5
#         )
#         self.assertAlmostEqual(
#             backtest_report.backtest_metrics.total_return_percentage, 0.0149, delta=0.001
#         )
#         end_time = time.time()
#         elapsed_time = end_time - start_time
#         print(f"Test completed in {elapsed_time:.2f} seconds")
#
#         snapshots = backtest_report.backtest_results.get_portfolio_snapshots()
#         # Check that the first two snapshots created at are the same
#         # as the start date of the backtest
#         self.assertEqual(
#             snapshots[0].created_at.replace(tzinfo=timezone.utc),
#             start_date.replace(tzinfo=timezone.utc)
#         )
