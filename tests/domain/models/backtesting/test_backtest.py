import os
from datetime import datetime, date, timezone
import tempfile
import unittest
from pathlib import Path
import polars as pl

from investing_algorithm_framework.domain import Backtest, Order, Position, \
    PortfolioSnapshot, BacktestMetrics, BacktestPermutationTest, \
    Trade, BacktestRun, BacktestSummaryMetrics, BacktestDateRange


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

        # Test models
        self.backtest_metrics_run_one = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        self.backtest_run_one = BacktestRun(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=self.backtest_metrics_run_one
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        self.permutation_test_metrics_one = BacktestPermutationTest(
            real_metrics=self.backtest_metrics_run_one,
            permutated_metrics=[self.backtest_metrics_run_one, self.backtest_metrics_run_one],
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

        self.backtest_summary_metrics_one = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )


    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_open(self):
        # Mock save and open methods
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run = BacktestRun(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        permutation_test_metrics = BacktestPermutationTest(
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

        backtest_metrics = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )


        # Create a Backtest instance
        backtest = Backtest(
            backtest_runs=[backtest_run],
            backtest_permutation_tests=[permutation_test_metrics],
            backtest_summary=backtest_metrics,
            metadata={"strategy": "test_strategy"},
            risk_free_rate=0.02
        )

        # Save the backtest
        backtest.save(self.dir_path)
        self.assertTrue((self.dir_path / "runs").exists())

        # Check that there is at least one results file
        results_dir = (self.dir_path / "runs")
        self.assertEqual(1, (len(os.listdir(results_dir))))

        # Get the first run
        first_run_dir = results_dir / os.listdir(results_dir)[0]
        self.assertTrue((first_run_dir / "run.json").exists())
        self.assertTrue((first_run_dir / "metrics.json").exists())

        # Check that there is a permutation tests directory
        self.assertTrue((self.dir_path / "permutation_tests").exists())

        # Check if there are 2 permutated_metrics folders
        permutated_metrics_dir = (self.dir_path / "permutation_tests")

        self.assertEqual(1, (len(os.listdir(permutated_metrics_dir))))
        self.assertTrue((self.dir_path / "metadata.json").exists())
        self.assertTrue((self.dir_path / "summary.json").exists())

        loaded_backtest = Backtest.open(self.dir_path)
        self.assertEqual(
            len(loaded_backtest.get_all_backtest_runs()), 1
        )
        self.assertEqual(
            len(loaded_backtest.get_all_backtest_permutation_tests()),
            1
        )
        self.assertEqual(
            1, len(loaded_backtest.backtest_permutation_tests)
        )

        first_backtest_run = loaded_backtest.get_all_backtest_runs()[0]
        self.assertEqual(
            first_backtest_run.trading_symbol, "EUR"
        )
        self.assertEqual(
            first_backtest_run.backtest_start_date,
            datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(
            first_backtest_run.backtest_end_date,
            datetime(2020, 12, 31, tzinfo=timezone.utc)
        )
        self.assertEqual(
            first_backtest_run.initial_unallocated, 1000.0
        )
        self.assertEqual(
            len(first_backtest_run.portfolio_snapshots), 2
        )
        self.assertEqual(
            len(first_backtest_run.trades), 1
        )
        self.assertEqual(
            len(first_backtest_run.orders), 1
        )
        self.assertEqual(
            len(first_backtest_run.positions), 1
        )

        backtest_metrics = first_backtest_run.backtest_metrics
        self.assertIsInstance(backtest_metrics, BacktestMetrics)
        self.assertEqual(backtest_metrics.cagr, 1.0)
        self.assertEqual(backtest_metrics.sharpe_ratio, 0.0)
        self.assertEqual(backtest_metrics.sortino_ratio, 0.0)
        self.assertEqual(backtest_metrics.calmar_ratio, 0.0)
        self.assertEqual(backtest_metrics.profit_factor, 0.0)
        self.assertEqual(backtest_metrics.annual_volatility, 0.0)

    def test_open_with_backtest_date_ranges(self):
        backtest_date_range_one = BacktestDateRange(
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2020, 12, 31, tzinfo=timezone.utc),
            name="Range 1"
        )
        backtest_date_range_two = BacktestDateRange(
            start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2021, 12, 31, tzinfo=timezone.utc),
            name="Range 2"
        )
        # Mock save and open methods
        backtest_metrics = BacktestMetrics(
            backtest_start_date=backtest_date_range_one.start_date,
            backtest_end_date=backtest_date_range_one.end_date,
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run = BacktestRun(
            backtest_start_date=backtest_date_range_one.start_date,
            backtest_end_date=backtest_date_range_one.end_date,
            backtest_date_range_name=backtest_date_range_one.name,
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )

        # Mock save and open methods
        backtest_metrics_two = BacktestMetrics(
            backtest_start_date=backtest_date_range_two.start_date,
            backtest_end_date=backtest_date_range_two.end_date,
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run_two = BacktestRun(
            backtest_start_date=backtest_date_range_two.start_date,
            backtest_end_date=backtest_date_range_two.end_date,
            backtest_date_range_name=backtest_date_range_two.name,
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics_two
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        permutation_test_metrics = BacktestPermutationTest(
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

        backtest_metrics = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )

        # Create a Backtest instance
        backtest = Backtest(
            backtest_runs=[backtest_run, backtest_run_two],
            backtest_permutation_tests=[permutation_test_metrics],
            backtest_summary=backtest_metrics,
            metadata={"strategy": "test_strategy"},
            risk_free_rate=0.02
        )

        # Save the backtest
        backtest.save(self.dir_path)
        self.assertTrue((self.dir_path / "runs").exists())

        # Check that there is at least one results file
        results_dir = (self.dir_path / "runs")
        self.assertEqual(2, (len(os.listdir(results_dir))))

        # Get the first run
        first_run_dir = results_dir / os.listdir(results_dir)[0]
        self.assertTrue((first_run_dir / "run.json").exists())
        self.assertTrue((first_run_dir / "metrics.json").exists())

        # Check that there is a permutation tests directory
        self.assertTrue((self.dir_path / "permutation_tests").exists())

        # Check if there are 1 permutated_metrics folders
        permutated_metrics_dir = (self.dir_path / "permutation_tests")

        self.assertEqual(1, (len(os.listdir(permutated_metrics_dir))))
        self.assertTrue((self.dir_path / "metadata.json").exists())
        self.assertTrue((self.dir_path / "summary.json").exists())

        loaded_backtest = Backtest.open(self.dir_path)
        self.assertEqual(
            len(loaded_backtest.get_all_backtest_runs()), 2
        )
        self.assertEqual(
            len(loaded_backtest.get_all_backtest_permutation_tests()),
            1
        )

        first_backtest_run = loaded_backtest.get_all_backtest_runs()[0]
        self.assertEqual(
            first_backtest_run.trading_symbol, "EUR"
        )
        self.assertEqual(
            first_backtest_run.backtest_start_date,
            backtest_date_range_one.start_date
        )
        self.assertEqual(
            first_backtest_run.backtest_end_date,
            backtest_date_range_one.end_date
        )
        self.assertEqual(
            first_backtest_run.initial_unallocated, 1000.0
        )
        self.assertEqual(
            len(first_backtest_run.portfolio_snapshots), 2
        )
        self.assertEqual(
            len(first_backtest_run.trades), 1
        )
        self.assertEqual(
            len(first_backtest_run.orders), 1
        )
        self.assertEqual(
            len(first_backtest_run.positions), 1
        )

        backtest_metrics = first_backtest_run.backtest_metrics
        self.assertIsInstance(backtest_metrics, BacktestMetrics)
        self.assertEqual(backtest_metrics.cagr, 1.0)
        self.assertEqual(backtest_metrics.sharpe_ratio, 0.0)
        self.assertEqual(backtest_metrics.sortino_ratio, 0.0)
        self.assertEqual(backtest_metrics.calmar_ratio, 0.0)
        self.assertEqual(backtest_metrics.profit_factor, 0.0)
        self.assertEqual(backtest_metrics.annual_volatility, 0.0)

        # Load only the first backtest run by date range name
        loaded_backtest = Backtest.open(
            self.dir_path,
            backtest_date_ranges=[backtest_date_range_one]
        )

        self.assertEqual(
            len(loaded_backtest.get_all_backtest_runs()), 1
        )

    def test_backtest_hash(self):
        # Mock save and open methods
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run = BacktestRun(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        permutation_test_metrics = BacktestPermutationTest(
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

        backtest_metrics = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )

        # Create a Backtest instance
        backtest = Backtest(
            backtest_runs=[backtest_run],
            backtest_permutation_tests=[permutation_test_metrics],
            backtest_summary=backtest_metrics,
            metadata={"strategy": "test_strategy"},
            risk_free_rate=0.02
        )

        # Mock save and open methods
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=1.0,
            total_growth_percentage=1.0,
            total_net_gain=1.0,
            total_net_gain_percentage=1.0,
            final_value=1.0,
            cagr=1.0,
            sharpe_ratio=0.0,
            rolling_sharpe_ratio=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            annual_volatility=0.0,
            monthly_returns=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns=[
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series=[
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)),
                (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)),
                (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)),
                (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)),
                (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown=0.0,
            max_drawdown_absolute=0.0,
            max_daily_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            trade_per_day=0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
            best_trade=Trade(
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
            worst_trade=Trade(
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
            average_trade_duration=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
            percentage_winning_months=0.0,
            percentage_winning_years=0.0,
            average_monthly_return=0.0,
            average_monthly_return_losing_months=0.0,
            average_monthly_return_winning_months=0.0,
            best_month=(0.0, datetime(2020, 1, 1)),
            best_year=(0.0, date(2020, 1, 1)),
            worst_month=(0.0, datetime(2020, 1, 1)),
            worst_year=(0.0, date(2020, 1, 1))
        )

        backtest_run_two = BacktestRun(
            backtest_start_date=datetime(2021, 1, 1),
            backtest_end_date=datetime(2023, 12, 31),
            trading_symbol="EUR",
            initial_unallocated=1000.0,
            number_of_runs=50,
            portfolio_snapshots=[
                PortfolioSnapshot(
                    created_at=datetime(2020, 1, 1),
                    total_value=1000.0,
                    unallocated=1000.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                ),
                PortfolioSnapshot(
                    created_at=datetime(2020, 12, 31),
                    total_value=1100.0,
                    unallocated=100.0,
                    pending_value=100.0,
                    cash_flow=0.0,
                    total_cost=0.0,
                )
            ],
            trades=[
                Trade(
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
                )
            ],
            orders=[
                Order(
                    id=1,
                    order_type="LIMIT",
                    price=100.0,
                    amount=0.1,
                    target_symbol="BTC",
                    trading_symbol="EUR",
                    created_at=datetime(2020, 1, 1),
                    updated_at=datetime(2020, 1, 1),
                    status="CLOSED",
                    remaining=10.0,
                    filled=10,
                    cost=1000.0,
                    order_side="BUY"
                )
            ],
            positions=[
                Position(
                    symbol="BTC/EUR",
                    amount=0.1,
                )
            ],
            created_at=datetime(2020, 1, 1),
            symbols=["BTC/EUR"],
            number_of_days=0,
            number_of_trades=0,
            number_of_trades_closed=0,
            number_of_trades_open=0,
            number_of_orders=0,
            number_of_positions=0,
            backtest_metrics=backtest_metrics
        )

        # ohlcv_csv_path = os
        ohlcv_df = pl.read_csv(self.ohlcv_csv_path).to_pandas()

        permutation_test_metrics = BacktestPermutationTest(
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

        backtest_metrics = BacktestSummaryMetrics(
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            profit_factor=0.0,
            annual_volatility=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            trades_per_year=0.0,
            number_of_trades=0,
            win_rate=0.0,
            win_loss_ratio=0.0,
        )

        # Create a Backtest instance
        backtest_two = Backtest(
            backtest_runs=[backtest_run_two],
            backtest_permutation_tests=[permutation_test_metrics],
            backtest_summary=backtest_metrics,
            metadata={"strategy": "test_strategy", "params": {"param1": 1, "param2": 2}},
            risk_free_rate=0.02
        )

        backtest_dict = {
            backtest: "backtest_one",
            backtest_two: "backtest_two"
        }
        self.assertEqual(2, len(backtest_dict))
        self.assertTrue(
            backtest in backtest_dict
        )
        self.assertTrue(
            backtest_two in backtest_dict
        )

    def test_add_permutation_metrics_after_backtest_has_been_save(self):
        backtest = Backtest(
            backtest_runs=[self.backtest_run_one],
            backtest_permutation_tests=[],
            backtest_summary=self.backtest_summary_metrics_one,
            metadata={"strategy": "test_strategy"},
            risk_free_rate=0.02
        )

        # Save the backtest
        backtest.save(self.dir_path)

        loaded_backtest = Backtest.open(self.dir_path)

        self.assertEqual(
            len(loaded_backtest.get_all_backtest_permutation_tests()), 0
        )

        # Add a permutation test
        loaded_backtest.add_permutation_test(
            self.permutation_test_metrics_one
        )

        # Save again
        loaded_backtest.save(self.dir_path)

        # Load again
        reloaded_backtest = Backtest.open(self.dir_path)
        self.assertEqual(
            len(reloaded_backtest.get_all_backtest_permutation_tests()),
            1
        )
