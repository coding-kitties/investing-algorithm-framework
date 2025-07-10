import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from investing_algorithm_framework import get_cagr


# Mock Snapshot class
class Snapshot:
    def __init__(self, total_value, created_at):
        self.total_value = total_value
        self.created_at = created_at

class TestGetCagr(unittest.TestCase):

    def create_report(self, prices, start_date):
        """ Helper to create a mocked BacktestReport from a price list """
        snapshots = [
            Snapshot(net_size, start_date + timedelta(weeks=i))
            for i, net_size in enumerate(prices)
        ]
        report = MagicMock()
        report.get_snapshots.return_value = snapshots
        return report

    def test_cagr_for_return_less_then_a_year(self):
        """
        Test a scenario where the CAGR is calculated 
        for a period less than a year (3 months). Given that the 
        portfolio return 12% annually, 
        the CAGR should be approximately 3% for 3 months.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1  # ≈ 0.0022
        weeks = 13  # 3 months ≈ 13 weeks

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [start_price * ((1 + weekly_return) ** i) for i in range(weeks + 1)]

        start_date = datetime(2022, 1, 1)
        report_x = self.create_report(prices, start_date)

        cagr = get_cagr(report_x)
        self.assertAlmostEqual(cagr, 0.12034875793587707, delta=1)

    def test_cagr_for_return_exactly_a_year(self):
        """
        Test a scenario where the CAGR is calculated
        for a period less than a year (3 months). Given that the
        portfolio return 12% annually,
        the CAGR should be approximately 3% for 3 months.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1  # ≈ 0.0022
        weeks = 52

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [start_price * ((1 + weekly_return) ** i) for i in range(weeks + 1)]

        start_date = datetime(2022, 1, 1)
        report_x = self.create_report(prices, start_date)

        cagr = get_cagr(report_x)
        self.assertAlmostEqual(cagr, 0.12034875793587663, delta=1)

    def test_cagr_for_return_more_then_a_year(self):
        """
        Test a scenario where the CAGR is calculated
        for a period less than a year (3 months). Given that the
        portfolio return 12% annually,
        the CAGR should be approximately 3% for 3 months.
        """
        # Convert annualized return to approximate weekly returns
        weekly_return = (1 + 0.12) ** (1 / 52) - 1  # ≈ 0.0022
        weeks = 73

        # Generate weekly prices (cumulative compounding)
        start_price = 100
        prices = [start_price * ((1 + weekly_return) ** i) for i in range(weeks + 1)]

        start_date = datetime(2022, 1, 1)
        report_x = self.create_report(prices, start_date)

        cagr = get_cagr(report_x)
        self.assertAlmostEqual(cagr, 0.1203487579358764, delta=1)
