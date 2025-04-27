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

    def test_get_orders(self):
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing/test_algorithm_backtest_created-at_2025-04-21-21-21"
        )
        report = load_backtest_report(path)
        self.assertEqual(
            len(report.get_orders()),
            305
        )
        self.assertEqual(
            len(report.get_orders(order_status="OPEN")),
            0
        )
        self.assertEqual(
            len(report.get_orders(order_status="CLOSED")),
            305
        )
        self.assertEqual(
            len(report.get_orders(target_symbol="BTC")),
            55
        )
        self.assertEqual(
            len(report.get_orders(target_symbol="SOL")),
            97
        )
        self.assertEqual(
            len(report.get_orders(target_symbol="ETH")),
            55
        )
        self.assertEqual(
            len(report.get_orders(target_symbol="DOT")),
            98
        )
        self.assertEqual(
            len(report.get_orders(order_status="CLOSED", target_symbol="BTC")),
            55
        )

    def test_get_trades(self):
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing/test_algorithm_backtest_created-at_2025-04-21-21-21"
        )
        report = load_backtest_report(path)

        self.assertEqual(
            len(report.get_trades(trade_status="OPEN")),
            4
        )
        self.assertEqual(
            len(report.get_trades(trade_status="CLOSED")),
            114
        )
        self.assertEqual(
            len(report.get_trades(target_symbol="BTC")),
            23
        )
        self.assertEqual(
            len(report.get_trades(target_symbol="SOL")),
            37
        )
        self.assertEqual(
            len(report.get_trades(target_symbol="ETH")),
            19
        )
        self.assertEqual(
            len(report.get_trades(target_symbol="DOT")),
            39
        )

    def test_get_symbols(self):
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing/test_algorithm_backtest_created-at_2025-04-21-21-21"
        )
        report = load_backtest_report(path)

        self.assertEqual(
            report.get_symbols(),
            {'SOL', 'ETH', 'DOT', 'BTC'}
        )

    def test_get_positions(self):
        path = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing/test_algorithm_backtest_created-at_2025-04-21-21-21"
        )
        report = load_backtest_report(path)

        self.assertEqual(
            len(report.get_positions()), 5
        )
        self.assertEqual(
            len(report.get_positions(symbol="BTC")),
            1
        )
        self.assertEqual(
            len(report.get_positions(symbol="SOL")),
            1
        )
        self.assertEqual(
            len(report.get_positions(symbol="ETH")),
            1
        )
        self.assertEqual(
            len(report.get_positions(symbol="DOT")),
            1
        )
