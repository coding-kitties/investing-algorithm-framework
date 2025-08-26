import os
from datetime import datetime, date
import tempfile
import unittest
from pathlib import Path
import polars as pl

from investing_algorithm_framework.domain import Backtest, \
    BacktestMetrics, BacktestPermutationTestMetrics, Trade


class TestBacktestSaveOpen(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create dummy strategy and data files
        self.strategy_file = self.dir_path / "strategy.py"
        self.strategy_file.write_text("print('strategy')")

        self.data_file = self.dir_path / "data.csv"
        self.data_file.write_text("date,open,high,low,close,volume\n")

        self.resource_dir = os.path.abspath(
            os.path.join(
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
                    os.pardir
                ),
                "resources"
            )
        )
        self.ohlcv_csv_path = os.path.join(
            self.resource_dir,
            "backtest_data/OHLCV_BTC-EUR_BINANCE_2h_2020-12-15-06-00_2021-01-01-00-30.csv"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_open(self):
        # Mock save and open methods
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve = [
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            growth = 0.0,
            growth_percentage = 0.0,
            total_net_gain = 0.0,
            total_net_gain_percentage = 0.0,
            final_value = 0.0,
            cagr = 0.0,
            sharpe_ratio = 0.0,
            rolling_sharpe_ratio = [
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio = 0.0,
            calmar_ratio = 0.0,
            profit_factor = 0.0,
            gross_profit = 0.0,
            gross_loss = 0.0,
            annual_volatility = 0.0,
            monthly_returns = [
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 2, 1)), (0.0, date(2020, 3, 1)),
                (0.0, date(2020, 4, 1)), (0.0, date(2020, 5, 1)), (0.0, date(2020, 6, 1)),
                (0.0, date(2020, 7, 1)), (0.0, date(2020, 8, 1)), (0.0, date(2020, 9, 1)),
                (0.0, date(2020, 10, 1)), (0.0, date(2020, 11, 1)), (0.0, date(2020, 12, 1))
            ],
            yearly_returns = [
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series = [
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 2, 1)), (0.0, date(2020, 3, 1)),
                (0.0, date(2020, 4, 1)), (0.0, date(2020, 5, 1)), (0.0, date(2020, 6, 1)),
                (0.0, date(2020, 7, 1)), (0.0, date(2020, 8, 1)), (0.0, date(2020, 9, 1)),
                (0.0, date(2020, 10, 1)), (0.0, date(2020, 11, 1)), (0.0, date(2020, 12, 1))
            ],
            max_drawdown = 0.0,
            max_drawdown_absolute = 0.0,
            max_daily_drawdown = 0.0,
            max_drawdown_duration = 0,
            trades_per_year = 0.0,
            trade_per_day = 0.0,
            exposure_factor = 0.0,
            trades_average_gain = (0.0, 0.0),
            trades_average_loss = (0.0, 0.0),
            best_trade = Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            worst_trade = Trade(
                id=10,
                open_price=0.0,
                opened_at=datetime(2020, 1, 1),
                closed_at=datetime(2020, 12, 31),
                orders=[],
                target_symbol="BTC",
                trading_symbol="EUR",
                amount=10.0,
                cost=1.0,
                available_amount=1.0,
                remaining=9.0,
                filled_amount=1,
                status="closed"
            ),
            average_trade_duration = 0.0,
            number_of_trades = 0,
            win_rate = 0.0,
            win_loss_ratio = 0.0,
            percentage_winning_months = 0.0,
            percentage_winning_years = 0.0,
            average_monthly_return = 0.0,
            average_monthly_return_losing_months = 0.0,
            average_monthly_return_winning_months = 0.0,
            best_month = (0.0, datetime(2020, 1, 1)),
            best_year = (0.0, date(2020, 1, 1)),
            worst_month = (0.0, datetime(2020, 1, 1)),
            worst_year = (0.0, date(2020, 1, 1))
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        permutation_test_metrics = BacktestPermutationTestMetrics(
            real_metrics=backtest_metrics,
            permutated_metrics=[backtest_metrics, backtest_metrics],
            p_values={
                "cagr": 0.05,
                "sharpe_ratio": 0.05,
                "sortino_ratio": 0.05,
                "calmar_ratio": 0.05,
                "profit_factor": 0.05,
                "annual_volatility": 0.05,
                "max_drawdown": 0.05,
                "win_rate": 0.05,
                "win_loss_ratio": 0.05,
                "average_monthly_return": 0.05
            },
            ohlcv_original_datasets={
                "BTC/EUR": ohlcv_df
            },
            ohlcv_permutated_datasets={
                "BTC/EUR": [ohlcv_df]
            }
        )

        # Create a Backtest instance
        backtest = Backtest(
            backtest_metrics=backtest_metrics,
            backtest_permutation_test_metrics=permutation_test_metrics,
        )

        # Save the backtest
        backtest.save(self.dir_path)

        # Check that files were created
        self.assertTrue((self.dir_path / "metrics.json").exists())

        # Check that there is a permutation tests directory
        self.assertTrue((self.dir_path / "permutation_tests").exists())

        # Check if the original metrics are in the permutation tests folder
        self.assertTrue(
            (self.dir_path / "permutation_tests" / "original_metrics").exists()
        )

        # Check if the permuted metrics are in the permutation tests folder
        self.assertTrue(
            (self.dir_path / "permutation_tests" / "permuted_metrics").exists()
        )

        # Check if their are 2 permutated_metrics folders
        permutated_metrics_dir = (self.dir_path / "permutation_tests" / "permuted_metrics")

        self.assertEqual(2, (len(os.listdir(permutated_metrics_dir))))

        # Check if the p-values are saved
        self.assertTrue((self.dir_path / "permutation_tests" / "p_values.json").exists())

    # def test_open_nonexistent_directory(self):
    #     with self.assertRaises(OperationalException):
    #         Backtest.open("nonexistent_dir")
