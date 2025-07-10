import os
from unittest import TestCase

from investing_algorithm_framework.app import pretty_print_backtest, \
    BacktestReport
from investing_algorithm_framework.domain import Backtest


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
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing/test_algorithm_backtest_created-at_2025-04-21-21-21"
        )
        report = Backtest.open(path)
        pretty_print_backtest(report)
