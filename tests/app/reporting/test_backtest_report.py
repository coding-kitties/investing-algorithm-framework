import os
from unittest import TestCase

from investing_algorithm_framework.app import Algorithm, \
    BacktestReport
from investing_algorithm_framework.domain import BacktestResult, \
    BacktestDateRange, PortfolioSnapshot
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
                created_at="2023-08-07 07:59:00",
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
        results = BacktestResult(
            name="test",
            backtest_date_range=BacktestDateRange(
                start_date="2023-08-07 07:59:00",
                end_date="2023-12-02 00:00:00",
                name="Test Backtest Date Range"
            ),
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=snapshots,
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000
        )
        data_files = [
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv",
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-22-00_2023-12-25-00-00.csv",
        ]

        report = BacktestReport.create(
            results=results,
            risk_free_rate=0.0,
            data_files=data_files,
            algorithm=algorithm,
        )
        output_path = os.path.join(self.resource_dir, "backtest_report")
        report.save(output_path)

        # Check if the report was saved correctly
        self.assertTrue(os.path.exists(output_path))

        # Check if the strategy directory was created
        strategy_dir = os.path.join(output_path, "strategies")
        self.assertTrue(os.path.exists(strategy_dir))

        # Check if the strategy.py file exists within the strategy directory
        strategy_file_path = os.path.join(strategy_dir, "strategy_one.py")
        self.assertTrue(os.path.exists(strategy_file_path))

        # Check if the report HTML file exists
        report_html_path = os.path.join(output_path, "report.html")
        self.assertTrue(os.path.exists(report_html_path))

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
        algorithm = Algorithm()
        # algorithm.add_strategy(StrategyOne)
        snapshots = [
            PortfolioSnapshot(
                created_at="2023-08-07 07:59:00",
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
        results = BacktestResult(
            name="test",
            backtest_date_range=BacktestDateRange(
                start_date="2023-08-07 07:59:00",
                end_date="2023-12-02 00:00:00",
                name="Test Backtest Date Range"
            ),
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=snapshots,
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000
        )
        data_files = [
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv",
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-22-00_2023-12-25-00-00.csv",
        ]

        report = BacktestReport.create(
            results=results,
            risk_free_rate=0.0,
            data_files=data_files,
            algorithm=algorithm,
            strategy_directory_path=os.path.join(
                self.resource_dir, "strategies_for_testing"
            ),
        )
        output_path = os.path.join(self.resource_dir, "backtest_report")
        report.save(output_path)

        # Check if the report was saved correctly
        self.assertTrue(os.path.exists(output_path))

        # Check if the strategy directory was created
        strategy_dir = os.path.join(output_path, "strategies")
        self.assertTrue(os.path.exists(strategy_dir))

        # Check if the strategy.py file exists within the strategy directory
        strategy_file_path = os.path.join(strategy_dir, "strategy_one.py")
        self.assertTrue(os.path.exists(strategy_file_path))

        # Check if the report HTML file exists
        report_html_path = os.path.join(output_path, "report.html")
        self.assertTrue(os.path.exists(report_html_path))

        # Check if the metrics JSON file exists
        metrics_json_path = os.path.join(output_path, "metrics.json")
        self.assertTrue(os.path.exists(metrics_json_path))


        # Check if the results were saved correctly
        self.assertTrue(os.path.exists(os.path.join(output_path, "results.json")))
        self.assertTrue(os.path.exists(os.path.join(output_path, "strategies")))

    def test_open(self):
        """
        Test the open method of the BacktestReport class, which should open the report in a web browser.
        """
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        snapshots = [
            PortfolioSnapshot(
                created_at="2023-08-07 07:59:00",
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
        results = BacktestResult(
            name="test",
            backtest_date_range=BacktestDateRange(
                start_date="2023-08-07 07:59:00",
                end_date="2023-12-02 00:00:00",
                name="Test Backtest Date Range"
            ),
            orders=[],
            trades=[],
            positions=[],
            portfolio_snapshots=snapshots,
            trading_symbol="EUR",
            number_of_runs=1000,
            initial_unallocated=1000
        )
        data_files = [
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_2h_2023-08-07-07-59_2023-12-02-00-00.csv",
            "tests/resources/market_data_sources_for_testing/OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-22-00_2023-12-25-00-00.csv",
        ]

        report = BacktestReport.create(
            results=results,
            risk_free_rate=0.0,
            data_files=data_files,
            algorithm=algorithm,
        )
        output_path = os.path.join(self.resource_dir, "backtest_report")
        report.save(output_path)

        # Open the report in a web browser
        report = BacktestReport.open(output_path)


        # Check if the strategy related paths were set correctly
        strategy_related_paths = report.strategy_related_paths
        self.assertEqual(len(strategy_related_paths), 3)

        # Check if the HTML report was loaded
        self.assertIsNotNone(report.html_report)

        # Check if the metrics was loaded
        self.assertIsNotNone(report.metrics)

        # Check if the results were loaded
        self.assertIsNotNone(report.results)

        # Check if the data files were loaded
        self.assertEqual(len(report.data_files), 2)
