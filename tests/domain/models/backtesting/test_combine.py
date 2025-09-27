from unittest import TestCase
from investing_algorithm_framework.domain import BacktestMetrics, \
    BacktestSummaryMetrics, Trade, generate_backtest_summary_metrics
from datetime import datetime, date

class TestCombine(TestCase):

    def test_add(self):
        # Metrics one: a winning backtest
        metrics_one = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[(1000, datetime(2020, 1, 1)),
                          (1500, datetime(2020, 12, 31))],
            total_growth=500,
            total_growth_percentage=50.0,
            total_net_gain=500,
            total_net_gain_percentage=50.0,
            final_value=1500.0,
            cagr=0.1,
            sharpe_ratio=1.2,
            rolling_sharpe_ratio=[],
            sortino_ratio=1.0,
            calmar_ratio=0.8,
            profit_factor=1.5,
            gross_profit=700,
            gross_loss=-200,
            annual_volatility=0.15,
            monthly_returns=[],
            yearly_returns=[],
            drawdown_series=[],
            max_drawdown=0.15,
            max_drawdown_absolute=100,
            max_daily_drawdown=-50,
            max_drawdown_duration=10,
            trades_per_year=12,
            trade_per_day=0.05,
            exposure_ratio=0.6,
            average_trade_gain=50,
            average_trade_gain_percentage=5.0,
            average_trade_loss=-20,
            average_trade_loss_percentage=-2.0,
            best_trade=Trade(id=1, open_price=100,
                             opened_at=datetime(2020, 1, 1),
                             closed_at=datetime(2020, 2, 1), orders=[],
                             target_symbol="BTC", trading_symbol="EUR",
                             amount=1, cost=100, available_amount=1,
                             remaining=0, filled_amount=1, status="closed"),
            worst_trade=Trade(id=2, open_price=100,
                              opened_at=datetime(2020, 3, 1),
                              closed_at=datetime(2020, 4, 1), orders=[],
                              target_symbol="BTC", trading_symbol="EUR",
                              amount=1, cost=100, available_amount=1,
                              remaining=0, filled_amount=1, status="closed"),
            average_trade_duration=5.0,
            number_of_trades=10,
            win_rate=0.7,
            win_loss_ratio=1.5,
            percentage_winning_months=0.6,
            percentage_winning_years=1.0,
            average_monthly_return=0.04,
            average_monthly_return_losing_months=-0.02,
            average_monthly_return_winning_months=0.08,
            best_month=(0.10, datetime(2020, 5, 1)),
            best_year=(0.5, date(2020, 12, 31)),
            worst_month=(-0.05, datetime(2020, 3, 1)),
            worst_year=(-0.1, date(2020, 12, 31)),
        )

        # Metrics two: a losing backtest
        metrics_two = BacktestMetrics(
            backtest_start_date=datetime(2021, 1, 1),
            backtest_end_date=datetime(2021, 12, 31),
            equity_curve=[(2000, datetime(2021, 1, 1)),
                          (1800, datetime(2021, 12, 31))],
            total_growth=-200,
            total_growth_percentage=-10.0,
            total_net_gain=-200,
            total_net_gain_percentage=-10.0,
            final_value=1800.0,
            cagr=-0.05,
            sharpe_ratio=-0.5,
            rolling_sharpe_ratio=[],
            sortino_ratio=-0.4,
            calmar_ratio=-0.3,
            profit_factor=0.7,
            gross_profit=300,
            gross_loss=-500,
            annual_volatility=0.25,
            monthly_returns=[],
            yearly_returns=[],
            drawdown_series=[],
            max_drawdown=0.2,
            max_drawdown_absolute=400,
            max_daily_drawdown=-150,
            max_drawdown_duration=30,
            trades_per_year=24,
            trade_per_day=0.1,
            exposure_ratio=0.8,
            average_trade_gain=20,
            average_trade_gain_percentage=2.0,
            average_trade_loss=-50,
            average_trade_loss_percentage=-5.0,
            best_trade=Trade(id=3, open_price=200,
                             opened_at=datetime(2021, 1, 1),
                             closed_at=datetime(2021, 2, 1), orders=[],
                             target_symbol="ETH", trading_symbol="EUR",
                             amount=2, cost=200, available_amount=2,
                             remaining=0, filled_amount=2, status="closed"),
            worst_trade=Trade(id=4, open_price=200,
                              opened_at=datetime(2021, 3, 1),
                              closed_at=datetime(2021, 4, 1), orders=[],
                              target_symbol="ETH", trading_symbol="EUR",
                              amount=2, cost=200, available_amount=2,
                              remaining=0, filled_amount=2, status="closed"),
            average_trade_duration=7.0,
            number_of_trades=20,
            win_rate=0.3,
            win_loss_ratio=0.6,
            percentage_winning_months=0.3,
            percentage_winning_years=0.0,
            average_monthly_return=-0.02,
            average_monthly_return_losing_months=-0.05,
            average_monthly_return_winning_months=0.03,
            best_month=(0.07, datetime(2021, 7, 1)),
            best_year=(0.2, date(2021, 12, 31)),
            worst_month=(-0.15, datetime(2021, 6, 1)),
            worst_year=(-0.2, date(2021, 12, 31)),
        )

        summary: BacktestSummaryMetrics = generate_backtest_summary_metrics(
            [metrics_one, metrics_two])

        # --- Assertions ---
        # Sum metrics
        self.assertEqual(summary.total_net_gain, 300)  # 500 + (-200)
        self.assertEqual(summary.total_loss, -700)  # -200 + -500
        self.assertEqual(summary.number_of_trades, 30)  # 10 + 20

        # Mean metrics
        self.assertAlmostEqual(summary.cagr, (0.1 + -0.05) / 2, places=2)
        self.assertAlmostEqual(summary.sharpe_ratio, (1.2 + -0.5) / 2, places=2)
        self.assertAlmostEqual(summary.sortino_ratio, (1.0 + -0.4) / 2, places=2)
        self.assertAlmostEqual(summary.calmar_ratio, (0.8 + -0.3) / 2, places=2)
        self.assertAlmostEqual(summary.profit_factor, (1.5 + 0.7) / 2, places=2)
        self.assertAlmostEqual(summary.win_rate, (0.7 + 0.3) / 2, places=2)

        # Extreme metrics
        self.assertEqual(summary.max_drawdown, 0.2)  # worst of the two
        self.assertEqual(summary.max_drawdown_duration, 30)  # longest
