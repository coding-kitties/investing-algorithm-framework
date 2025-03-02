import os
from unittest import TestCase

from investing_algorithm_framework.domain import BacktestReportsEvaluation, \
    pretty_print_backtest_reports_evaluation, load_backtest_reports


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

    def test_pretty_print(self):
        path = os.path.join(self.resource_dir, "backtest_reports_for_testing")
        reports = load_backtest_reports(path)
        evaluation = BacktestReportsEvaluation(reports)
        pretty_print_backtest_reports_evaluation(evaluation)
