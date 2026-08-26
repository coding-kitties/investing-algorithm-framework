from unittest import TestCase

from investing_algorithm_framework import Portfolio


class TestPortfolioToDict(TestCase):

    def test_to_dict_includes_pnl_and_volume_fields(self):
        portfolio = Portfolio(
            identifier="BITVAVO",
            trading_symbol="EUR",
            net_size=1200.0,
            unallocated=800.0,
            initial_balance=1000.0,
            market="BITVAVO",
            realized=150.0,
            total_revenue=5000.0,
            total_cost=4850.0,
            total_net_gain=150.0,
            total_trade_volume=9700.0,
        )

        data = portfolio.to_dict()

        self.assertEqual(1200.0, data["net_size"])
        self.assertEqual(150.0, data["realized"])
        self.assertEqual(5000.0, data["total_revenue"])
        self.assertEqual(4850.0, data["total_cost"])
        self.assertEqual(150.0, data["total_net_gain"])
        self.assertEqual(9700.0, data["total_trade_volume"])
