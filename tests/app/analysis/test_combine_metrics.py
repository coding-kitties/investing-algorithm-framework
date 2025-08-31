from unittest import TestCase
from datetime import datetime, date
from investing_algorithm_framework.domain import Trade, BacktestMetrics
from investing_algorithm_framework.app.analysis import combine_backtest_metrics

class TestCombineMetrics(TestCase):

    def test_combine_metrics(self):

        # Variation 1
        backtest_metrics_1 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (1.0, datetime(2020, 1, 1)),
                (1.5, datetime(2020, 6, 30)),
                (2.0, datetime(2020, 12, 31)),
            ],
            growth=1000.0,
            growth_percentage=100.0,
            total_net_gain=1000.0,
            total_net_gain_percentage=100.0,
            final_value=2000.0,
            cagr=0.15,
            sharpe_ratio=1.2,
            rolling_sharpe_ratio=[(0.5, datetime(2020, 6, 30)),
                                  (1.2, datetime(2020, 12, 31))],
            sortino_ratio=1.0,
            calmar_ratio=0.8,
            profit_factor=1.5,
            gross_profit=1500.0,
            gross_loss=500.0,
            annual_volatility=0.2,
            monthly_returns=[
                (0.05, datetime(2020, m, 1)) for m in range(1, 13)
            ],
            yearly_returns=[(1.0, date(2020, 12, 31))],
            drawdown_series=[(0.1, datetime(2020, 6, 30))],
            max_drawdown=0.2,
            max_drawdown_absolute=400.0,
            max_daily_drawdown=0.05,
            max_drawdown_duration=30,
            trades_per_year=50,
            trade_per_day=0.2,
            exposure_ratio=0.75,
            trades_average_gain=200,
            trades_average_gain_percentage=0.1,
            trades_average_loss=100,
            trades_average_loss_percentage=0.1,
            best_trade=Trade(id=1, open_price=100,
                             opened_at=datetime(2020, 1, 1),
                             closed_at=datetime(2020, 2, 1), orders=[],
                             target_symbol="BTC",
                             trading_symbol="EUR", amount=1, cost=100,
                             available_amount=1,
                             remaining=0, filled_amount=1, status="closed"),
            worst_trade=Trade(id=2, open_price=100,
                              opened_at=datetime(2020, 3, 1),
                              closed_at=datetime(2020, 4, 1), orders=[],
                              target_symbol="BTC",
                              trading_symbol="EUR", amount=1, cost=100,
                              available_amount=1,
                              remaining=0, filled_amount=1, status="closed"),
            average_trade_duration=2.5,
            number_of_trades=50,
            win_rate=0.55,
            win_loss_ratio=1.2,
            percentage_winning_months=60.0,
            percentage_winning_years=100.0,
            average_monthly_return=0.04,
            average_monthly_return_losing_months=-0.02,
            average_monthly_return_winning_months=0.08,
            best_month=(0.12, datetime(2020, 8, 1)),
            best_year=(1.0, date(2020, 12, 31)),
            worst_month=(-0.05, datetime(2020, 3, 1)),
            worst_year=(0.2, date(2020, 12, 31)),
        )

        # Variation 2
        backtest_metrics_2 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (1.0, datetime(2020, 1, 1)),
                (1.2, datetime(2020, 6, 30)),
                (1.4, datetime(2020, 12, 31)),
            ],
            growth=400.0,
            growth_percentage=40.0,
            total_net_gain=400.0,
            total_net_gain_percentage=40.0,
            final_value=1400.0,
            cagr=0.08,
            sharpe_ratio=0.6,
            rolling_sharpe_ratio=[(0.3, datetime(2020, 6, 30)),
                                  (0.6, datetime(2020, 12, 31))],
            sortino_ratio=0.5,
            calmar_ratio=0.4,
            profit_factor=1.2,
            gross_profit=1000.0,
            gross_loss=600.0,
            annual_volatility=0.15,
            monthly_returns=[
                (0.02, datetime(2020, m, 1)) for m in range(1, 13)
            ],
            yearly_returns=[(0.4, date(2020, 12, 31))],
            drawdown_series=[(0.15, datetime(2020, 7, 31))],
            max_drawdown=0.25,
            max_drawdown_absolute=350.0,
            max_daily_drawdown=0.06,
            max_drawdown_duration=40,
            trades_per_year=30,
            trade_per_day=0.12,
            exposure_ratio=0.6,
            trades_average_gain_percentage=0.07,
            trades_average_gain=140.0,
            trades_average_loss=-80.0,
            trades_average_loss_percentage=-0.04,
            best_trade=Trade(id=3, open_price=120,
                             opened_at=datetime(2020, 5, 1),
                             closed_at=datetime(2020, 6, 1), orders=[],
                             target_symbol="BTC",
                             trading_symbol="EUR", amount=1, cost=120,
                             available_amount=1,
                             remaining=0, filled_amount=1, status="closed"),
            worst_trade=Trade(id=4, open_price=100,
                              opened_at=datetime(2020, 7, 1),
                              closed_at=datetime(2020, 8, 1), orders=[],
                              target_symbol="BTC",
                              trading_symbol="EUR", amount=1, cost=100,
                              available_amount=1,
                              remaining=0, filled_amount=1, status="closed"),
            average_trade_duration=3.2,
            number_of_trades=30,
            win_rate=0.45,
            win_loss_ratio=0.9,
            percentage_winning_months=50.0,
            percentage_winning_years=100.0,
            average_monthly_return=0.025,
            average_monthly_return_losing_months=-0.03,
            average_monthly_return_winning_months=0.06,
            best_month=(0.08, datetime(2020, 10, 1)),
            best_year=(0.4, date(2020, 12, 31)),
            worst_month=(-0.06, datetime(2020, 4, 1)),
            worst_year=(0.1, date(2020, 12, 31)),
        )

        combined = combine_backtest_metrics(
            [backtest_metrics_1, backtest_metrics_2]
        )

        self.assertEqual(700, combined.total_net_gain)
        self.assertAlmostEqual(70.0, combined.total_net_gain_percentage)
        self.assertAlmostEqual(70.0, combined.growth_percentage)
        self.assertEqual(700.0, combined.growth)
        self.assertEqual(0.5, combined.win_rate)
