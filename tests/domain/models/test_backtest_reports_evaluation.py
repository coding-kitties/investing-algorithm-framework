import os
from unittest import TestCase

from investing_algorithm_framework import load_backtest_reports, \
    BacktestReportsEvaluation


class Test(TestCase):

    def setUp(self) -> None:
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

    def test_backtest_reports_evaluation(self):
        path = os.path.join(self.resource_dir, "backtest_reports_for_testing")
        reports = load_backtest_reports(path)
        evaluation = BacktestReportsEvaluation(reports)
        self.assertEqual(len(evaluation.backtest_reports), 6)
        first_backtest_report = evaluation.backtest_reports[0]
        time_frame = (
            first_backtest_report.backtest_start_date,
            first_backtest_report.backtest_end_date
        )
        self.assertEqual(
            "10-50-100", evaluation.profit_order[time_frame][0].name
        )
