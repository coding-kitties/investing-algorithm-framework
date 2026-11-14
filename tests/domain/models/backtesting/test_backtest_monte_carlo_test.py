import unittest
from types import SimpleNamespace

from investing_algorithm_framework import BacktestDateRange, BacktestWindow
from investing_algorithm_framework.app.app import App
from investing_algorithm_framework.domain.backtesting import \
    BacktestMonteCarloTest


class TestBacktestMonteCarloTest(unittest.TestCase):

    def setUp(self):
        self.backtest_window = BacktestWindow(train_range=BacktestDateRange(
            start_date="2024-01-01",
            end_date="2024-12-31",
            name="validation",
        ))

    def test_one_sided_p_values_respect_metric_direction(self):
        result = BacktestMonteCarloTest(
            real_metrics=SimpleNamespace(
                sharpe_ratio=2.0,
                max_drawdown=0.10,
            ),
            permutated_metrics=[
                SimpleNamespace(sharpe_ratio=1.0, max_drawdown=0.20),
                SimpleNamespace(sharpe_ratio=2.5, max_drawdown=0.30),
            ],
            backtest_window=self.backtest_window,
        )

        result.compute_p_values(
            metrics=["sharpe_ratio", "max_drawdown"]
        )

        self.assertEqual(0.5, result.p_values["sharpe_ratio"])
        self.assertEqual(0.0, result.p_values["max_drawdown"])

    def test_app_result_uses_the_requested_backtest_window(self):
        date_range = self.backtest_window.train_range
        metrics = SimpleNamespace(number_of_trades=1)
        backtest = SimpleNamespace(
            get_backtest_metrics=lambda requested_range: metrics
        )
        backtests = SimpleNamespace(
            iter_backtests=lambda: iter([backtest])
        )
        fake_app = SimpleNamespace(
            container=SimpleNamespace(
                backtest_service=lambda: SimpleNamespace(),
                data_provider_service=lambda: SimpleNamespace(),
            ),
            run_backtest=lambda **kwargs: backtests,
        )

        result = App.run_monte_carlo_test(
            fake_app,
            strategy=SimpleNamespace(data_sources=[]),
            backtest_date_range=date_range,
            number_of_permutations=0,
            market="BITVAVO",
            trading_symbol="EUR",
            show_progress=False,
        )

        self.assertEqual(date_range, result.backtest_window.train_range)


if __name__ == "__main__":
    unittest.main()
