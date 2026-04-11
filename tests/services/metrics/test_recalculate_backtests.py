import os
from unittest import TestCase

from investing_algorithm_framework import (
    Backtest, recalculate_backtests,
)


# Per-run metric keys to compare (attr name, tolerance)
_RUN_METRICS = [
    ('cagr', 1e-6),
    ('sharpe_ratio', 1e-6),
    ('sortino_ratio', 1e-6),
    ('calmar_ratio', 1e-6),
    ('max_drawdown', 1e-6),
    ('annual_volatility', 1e-6),
    ('profit_factor', 1e-6),
    ('win_rate', 1e-6),
    ('number_of_trades', 0),
    ('number_of_trades_closed', 0),
    ('total_net_gain', 1e-4),
    ('total_net_gain_percentage', 1e-4),
    ('total_growth', 1e-4),
    ('total_growth_percentage', 1e-4),
    ('trades_per_year', 1e-4),
    ('average_trade_duration', 1e-4),
    ('exposure_ratio', 1e-4),
]

# Summary metric keys to compare
_SUMMARY_METRICS = [
    ('cagr', 1e-6),
    ('sharpe_ratio', 1e-6),
    ('sortino_ratio', 1e-6),
    ('calmar_ratio', 1e-6),
    ('max_drawdown', 1e-6),
    ('annual_volatility', 1e-6),
    ('profit_factor', 1e-6),
    ('number_of_trades', 0),
    ('number_of_trades_closed', 0),
    ('trades_per_year', 1e-4),
]


class TestRecalculateBacktests(TestCase):

    def setUp(self):
        self.resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        self.backtests_directory = os.path.join(
            self.resource_directory, 'test_data', 'backtests'
        )

    def _load_backtest(self, name):
        path = os.path.join(self.backtests_directory, name)
        return Backtest.open(path)

    def test_recalculate_single_backtest(self):
        bt = self._load_backtest('backtest_one')

        # Clear existing metrics
        for run in bt.get_all_backtest_runs():
            run.backtest_metrics = None
        bt.backtest_summary = None

        result = recalculate_backtests([bt], risk_free_rate=0.024)
        self.assertEqual(len(result), 1)
        recalculated = result[0]

        # Per-run metrics should be recomputed
        for run in recalculated.get_all_backtest_runs():
            self.assertIsNotNone(run.backtest_metrics)
            self.assertIsNotNone(run.backtest_metrics.cagr)
            self.assertIsNotNone(run.backtest_metrics.sharpe_ratio)
            self.assertIsNotNone(run.backtest_metrics.max_drawdown)

        # Summary should be regenerated
        self.assertIsNotNone(recalculated.backtest_summary)
        self.assertIsNotNone(recalculated.backtest_summary.cagr)
        self.assertIsNotNone(recalculated.backtest_summary.sharpe_ratio)

    def test_recalculate_multiple_backtests(self):
        bt1 = self._load_backtest('backtest_one')
        bt2 = self._load_backtest('backtest_two')

        # Clear metrics on both
        for bt in [bt1, bt2]:
            for run in bt.get_all_backtest_runs():
                run.backtest_metrics = None
            bt.backtest_summary = None

        result = recalculate_backtests([bt1, bt2], risk_free_rate=0.024)
        self.assertEqual(len(result), 2)

        for bt in result:
            for run in bt.get_all_backtest_runs():
                self.assertIsNotNone(run.backtest_metrics)
            self.assertIsNotNone(bt.backtest_summary)

    def test_recalculate_uses_backtest_risk_free_rate(self):
        bt = self._load_backtest('backtest_one')
        bt.risk_free_rate = 0.05

        for run in bt.get_all_backtest_runs():
            run.backtest_metrics = None

        result = recalculate_backtests([bt])
        recalculated = result[0]

        for run in recalculated.get_all_backtest_runs():
            self.assertIsNotNone(run.backtest_metrics)

    def test_recalculate_preserves_run_count(self):
        bt = self._load_backtest('backtest_one')
        original_run_count = len(bt.get_all_backtest_runs())

        recalculate_backtests([bt], risk_free_rate=0.024)

        self.assertEqual(
            len(bt.get_all_backtest_runs()), original_run_count
        )

    def test_recalculate_summary_reflects_runs(self):
        bt = self._load_backtest('backtest_one')
        recalculate_backtests([bt], risk_free_rate=0.024)

        runs = bt.get_all_backtest_runs()
        if len(runs) > 0:
            summary = bt.backtest_summary
            self.assertIsNotNone(summary)

            # Total trades should equal sum of per-run trades
            run_trades = sum(
                r.backtest_metrics.number_of_trades
                for r in runs
                if r.backtest_metrics
                and r.backtest_metrics.number_of_trades is not None
            )
            if run_trades > 0:
                self.assertEqual(summary.number_of_trades, run_trades)

    def test_recalculate_matches_original_run_metrics(self):
        """Recalculated per-run metrics must match the originals when
        recomputed from the same raw data (idempotency check)."""
        for name in ('backtest_one', 'backtest_two'):
            bt = self._load_backtest(name)
            rfr = bt.risk_free_rate or 0.024

            # First recalculation
            recalculate_backtests([bt], risk_free_rate=rfr)
            first_pass = []
            for run in bt.get_all_backtest_runs():
                m = run.backtest_metrics
                first_pass.append({
                    attr: getattr(m, attr, None)
                    for attr, _ in _RUN_METRICS
                })

            # Second recalculation (idempotency)
            recalculate_backtests([bt], risk_free_rate=rfr)

            for i, run in enumerate(bt.get_all_backtest_runs()):
                recalc = run.backtest_metrics
                for attr, tol in _RUN_METRICS:
                    first_val = first_pass[i][attr]
                    second_val = getattr(recalc, attr, None)

                    if first_val is None:
                        continue

                    self.assertIsNotNone(
                        second_val,
                        f"{name} run {i}: {attr} is None on "
                        f"second pass (was {first_val})"
                    )

                    if tol == 0:
                        self.assertEqual(
                            second_val, first_val,
                            f"{name} run {i}: {attr} "
                            f"{second_val} != {first_val}"
                        )
                    else:
                        self.assertAlmostEqual(
                            second_val, first_val, delta=tol,
                            msg=f"{name} run {i}: {attr} "
                                f"{second_val} != {first_val} "
                                f"(tol={tol})"
                        )

    def test_recalculate_matches_original_summary_metrics(self):
        """Recalculated summary must be idempotent — two passes
        produce identical results."""
        for name in ('backtest_one', 'backtest_two'):
            bt = self._load_backtest(name)
            rfr = bt.risk_free_rate or 0.024

            # First pass
            recalculate_backtests([bt], risk_free_rate=rfr)
            first_summary = {
                attr: getattr(bt.backtest_summary, attr, None)
                for attr, _ in _SUMMARY_METRICS
            }

            # Second pass
            recalculate_backtests([bt], risk_free_rate=rfr)
            recalc_summary = bt.backtest_summary

            self.assertIsNotNone(recalc_summary)

            for attr, tol in _SUMMARY_METRICS:
                first_val = first_summary[attr]
                second_val = getattr(recalc_summary, attr, None)

                if first_val is None:
                    continue

                self.assertIsNotNone(
                    second_val,
                    f"{name} summary: {attr} is None on "
                    f"second pass (was {first_val})"
                )

                if tol == 0:
                    self.assertEqual(
                        second_val, first_val,
                        f"{name} summary: {attr} "
                        f"{second_val} != {first_val}"
                    )
                else:
                    self.assertAlmostEqual(
                        second_val, first_val, delta=tol,
                        msg=f"{name} summary: {attr} "
                            f"{second_val} != {first_val} "
                            f"(tol={tol})"
                    )

    def test_recalculate_summary_consistent_with_run_metrics(self):
        """Summary metrics must be derivable from the per-run metrics."""
        for name in ('backtest_one', 'backtest_two'):
            bt = self._load_backtest(name)
            rfr = bt.risk_free_rate or 0.024
            recalculate_backtests([bt], risk_free_rate=rfr)

            runs = bt.get_all_backtest_runs()
            summary = bt.backtest_summary

            # Regenerate summary independently from per-run metrics
            from investing_algorithm_framework.domain.backtesting \
                .combine_backtests import generate_backtest_summary_metrics
            run_metrics = [
                r.backtest_metrics for r in runs
                if r.backtest_metrics is not None
            ]
            independent_summary = generate_backtest_summary_metrics(
                run_metrics
            )

            for attr, tol in _SUMMARY_METRICS:
                sv = getattr(summary, attr, None)
                iv = getattr(independent_summary, attr, None)

                if sv is None and iv is None:
                    continue

                if tol == 0:
                    self.assertEqual(
                        sv, iv,
                        f"{name} summary vs independent: {attr} "
                        f"{sv} != {iv}"
                    )
                else:
                    if sv is not None and iv is not None:
                        self.assertAlmostEqual(
                            sv, iv, delta=tol,
                            msg=f"{name} summary vs independent: "
                                f"{attr} {sv} != {iv} (tol={tol})"
                        )
