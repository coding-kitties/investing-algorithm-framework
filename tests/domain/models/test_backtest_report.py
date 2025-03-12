import os
from unittest import TestCase
from datetime import datetime
from investing_algorithm_framework import load_backtest_report


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
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing",
            "report_950100_backtest-start-date_2021-12-21-00-00_"
            "backtest-end-date_2022-06-20-00-00"
            "_created-at_2024-04-25-13-52.json"
        )
        report = load_backtest_report(path)
        self.assertEqual(
            report.name, "950100"
        )
        self.assertEqual(
            datetime(year=2021, month=12, day=21),
            report.backtest_start_date
        )
        self.assertEqual(
            datetime(year=2022, month=6, day=20),
            report.backtest_end_date
        )
        self.assertEqual(10.713880999999981, report.total_net_gain)
        self.assertEqual(2.6784702499999753, report.growth_rate)
        self.assertEqual(2.6784702499999953, report.total_net_gain_percentage)
        self.assertEqual(2.6784702499999753, report.growth_rate)
        self.assertEqual(400.0, report.initial_unallocated)
        self.assertEqual(42, report.number_of_orders)
        self.assertEqual(2173, report.number_of_runs)
        self.assertEqual("EUR", report.trading_symbol)
