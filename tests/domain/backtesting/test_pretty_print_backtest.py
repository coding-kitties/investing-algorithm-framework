import os
from unittest import TestCase

from investing_algorithm_framework.domain import pretty_print_backtest, \
    load_backtest_report


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
            "backtest_reports_for_testing/report_GoldenCrossStrategy_backtest-start-date_2023-08-24-00-00_backtest-end-date_2023-12-02-00-00_created-at_2025-01-27-08-21.json"
        )
        report = load_backtest_report(path)
        pretty_print_backtest(report)
