from unittest import TestCase
from datetime import datetime, date
import tempfile
from pathlib import Path

from investing_algorithm_framework.domain import BacktestMetrics, Trade


class TestBacktestMetrics(TestCase):

    def setUp(self):
        # Create a temporary directory for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def test_save(self):
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve = [
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth = 0.0,
            total_growth_percentage = 0.0,
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
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)), (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)), (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)), (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)), (0.0, datetime(2020, 12, 1))
            ],
            yearly_returns = [
                (0.0, date(2020, 1, 1)), (0.0, date(2020, 12, 31))
            ],
            drawdown_series = [
                (0.0, datetime(2020, 1, 1)), (0.0, datetime(2020, 2, 1)), (0.0, datetime(2020, 3, 1)),
                (0.0, datetime(2020, 4, 1)), (0.0, datetime(2020, 5, 1)), (0.0, datetime(2020, 6, 1)),
                (0.0, datetime(2020, 7, 1)), (0.0, datetime(2020, 8, 1)), (0.0, datetime(2020, 9, 1)),
                (0.0, datetime(2020, 10, 1)), (0.0, datetime(2020, 11, 1)), (0.0, datetime(2020, 12, 1))
            ],
            max_drawdown = 0.0,
            max_drawdown_absolute = 0.0,
            max_daily_drawdown = 0.0,
            max_drawdown_duration = 0,
            trades_per_year = 0.0,
            trade_per_day = 0.0,
            exposure_ratio=0.0,
            average_trade_gain=0.0,
            average_trade_gain_percentage=0.0,
            average_trade_loss=0.0,
            average_trade_loss_percentage=0.0,
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

        file_path = self.dir_path / "backtest_metrics.json"
        backtest_metrics.save(file_path)

    def test_open(self):
        backtest_metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (0.0, datetime(2020, 1, 1)),
                (1.0, datetime(2020, 12, 31)),
                (0.5, datetime(2020, 6, 30)),
                (0.2, datetime(2020, 3, 31))
            ],
            total_growth=0.0,
            total_growth_percentage=0.0,
            total_net_gain=0.0,
            total_net_gain_percentage=0.0,
            final_value=0.0,
            cagr=0.0,
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

        file_path = self.dir_path / "backtest_metrics.json"
        backtest_metrics.save(file_path)

        loaded_metrics = BacktestMetrics.open(file_path)
        self.assertEqual(backtest_metrics.to_dict(), loaded_metrics.to_dict())
