import os
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.app import Algorithm
from investing_algorithm_framework.domain import  BacktestRun, \
    BacktestDateRange, PortfolioSnapshot, Backtest, BacktestMetrics
from tests.resources.strategies_for_testing.strategy_one import StrategyOne


class Test(TestCase):

    def setUp(self):
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

    def test_save_without_algorithm(self):
        """
        Test the save method of the BacktestReport class, as part of a backtest run. This means that the backtest report will be created
        with an Algorithm instance and a BacktestResult instance, which are required to create the report. Also, a risk-free rate is provided,
        to simulate an offline backtest run.
        """
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        snapshots = [
            PortfolioSnapshot(
                created_at="2023-08-07 07:00:00",
                total_value=1000,
                trading_symbol="EUR",
                unallocated=1000,
            ),
            PortfolioSnapshot(
                created_at="2023-12-02 00:00:00",
                total_value=1200,
                trading_symbol="EUR",
                unallocated=200,
            )
        ]
        backtest_date_range = BacktestDateRange(
            start_date="2023-08-07 07:00:00",
            end_date="2023-12-02 00:00:00",
            name="Test Backtest Date Range"
        )
        run = BacktestRun(
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=snapshots,
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000,
            created_at=datetime.now(tz=timezone.utc)
        )
        data_files = [
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv",
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-22-00_2023-12-25-00-00.csv",
        ]

        backtest = Backtest(
            backtest_runs=[run],
        )
        output_path = os.path.join(self.resource_dir, "backtest_report")
        backtest.save(output_path)

        # Check if the report was saved correctly
        self.assertTrue(os.path.exists(output_path))

        # Check if the strategy directory was created
        strategy_dir = os.path.join(output_path, "strategies")
        self.assertTrue(os.path.exists(strategy_dir))

        # Check if the strategy.py file exists within the strategy directory
        strategy_file_path = os.path.join(strategy_dir, "strategy_one.py")
        self.assertTrue(os.path.exists(strategy_file_path))

        # Check if the metrics JSON file exists
        metrics_json_path = os.path.join(output_path, "metrics.json")
        self.assertTrue(os.path.exists(metrics_json_path))


        # Check if the results were saved correctly
        self.assertTrue(os.path.exists(os.path.join(output_path, "results.json")))
        self.assertTrue(os.path.exists(os.path.join(output_path, "strategies")))

    def test_save_with_strategies_directory(self):
        """
        Test the save method of the BacktestReport class, as part of a backtest run. This means that the backtest report will be created
        with an Algorithm instance and a BacktestResult instance, which are required to create the report. Also, a risk-free rate is provided,
        to simulate an offline backtest run.
        """
        snapshots = [
            PortfolioSnapshot(
                created_at="2023-08-07 07:00:00",
                total_value=1000,
                trading_symbol="EUR",
                unallocated=1000,
            ),
            PortfolioSnapshot(
                created_at="2023-12-02 00:00:00",
                total_value=1200,
                trading_symbol="EUR",
                unallocated=200,
            )
        ]
        backtest_date_range = BacktestDateRange(
            start_date="2023-08-07 07:00:00",
            end_date="2023-12-02 00:00:00",
            name="Test Backtest Date Range"
        )
        results = BacktestRun(
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            created_at=datetime.now(tz=timezone.utc),
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=snapshots,
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000,
            backtest_metrics=BacktestMetrics(
                backtest_start_date=datetime(2023, 8, 7, 7, 59, tzinfo=None),
                backtest_end_date=datetime(2023, 8, 7, 7, 59, tzinfo=None),
                equity_curve=[],
                total_net_gain=0.2,
                cagr=0.1,
                sharpe_ratio=1.5,
                rolling_sharpe_ratio=[],
                sortino_ratio=1.2,
                profit_factor=1.5,
                calmar_ratio=0.8,
                annual_volatility=0.2,
                monthly_returns=[],
                yearly_returns=[],
                drawdown_series=[],
                max_drawdown=0.15,
                max_drawdown_absolute=0.2,
                max_daily_drawdown=0.05
            )
        )
        data_files = [
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv",
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-22-00_2023-12-25-00-00.csv",
        ]

        backtest = Backtest(
            backtest_runs=[results],
            risk_free_rate=0.0
        )
        output_path = os.path.join(self.resource_dir, "backtest_report")
        backtest.save(output_path)

        # Check if the report was saved correctly
        self.assertTrue(os.path.exists(output_path))

        # Check if the strategy directory was created
        strategy_dir = os.path.join(output_path, "strategies")
        self.assertTrue(os.path.exists(strategy_dir))

        # Check if the strategy.py file exists within the strategy directory
        strategy_file_path = os.path.join(strategy_dir, "strategy_one.py")
        self.assertTrue(os.path.exists(strategy_file_path))

        # Check if the metrics JSON file exists
        metrics_json_path = os.path.join(output_path, "metrics.json")
        self.assertTrue(os.path.exists(metrics_json_path))

        # Check if the results were saved correctly
        self.assertTrue(os.path.exists(os.path.join(output_path, "results.json")))
        self.assertTrue(os.path.exists(os.path.join(output_path, "strategies")))
