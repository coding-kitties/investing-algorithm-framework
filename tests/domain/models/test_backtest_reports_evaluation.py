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
        self.assertEqual(len(evaluation.backtest_reports), 3)
