from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework.domain import PortfolioSnapshot


class Test(TestCase):

    def test_to_dict(self):
        snapshot = PortfolioSnapshot(
            portfolio_id="portfolio_1",
            trading_symbol="BTC/USDT",
            pending_value=5000,
            unallocated=2000,
            net_size=3000,
            total_net_gain=1500,
            total_revenue=7000,
            total_cost=5500,
            total_value=8000,
            cash_flow=1000,
            created_at=datetime(
                2023,
                10,
                1,
                12,
                0,
                0,
                tzinfo=timezone.utc
            ),
            metadata={"strategy": "mean_reversion"},
        )
        snapshot_dict = snapshot.to_dict()
        self.assertEqual(snapshot_dict["portfolio_id"], "portfolio_1")
        self.assertEqual(snapshot_dict["trading_symbol"], "BTC/USDT")
        self.assertEqual(snapshot_dict["pending_value"], 5000)
        self.assertEqual(snapshot_dict["unallocated"], 2000)
        self.assertEqual(snapshot_dict["net_size"], 3000)
        self.assertEqual(snapshot_dict["total_net_gain"], 1500)
        self.assertEqual(snapshot_dict["total_revenue"], 7000)
        self.assertEqual(snapshot_dict["total_cost"], 5500)
        self.assertEqual(snapshot_dict["total_value"], 8000)
        self.assertEqual(snapshot_dict["cash_flow"], 1000)
        self.assertEqual(
            snapshot_dict["created_at"],
            "2023-10-01T12:00:00+00:00"
        )
        self.assertEqual(
            snapshot_dict["metadata"], {"strategy": "mean_reversion"}
        )

    def test_from_dict(self):
        snapshot_data = {
            "portfolio_id": "portfolio_1",
            "trading_symbol": "BTC/USDT",
            "pending_value": 5000,
            "unallocated": 2000,
            "net_size": 3000,
            "total_net_gain": 1500,
            "total_revenue": 7000,
            "total_cost": 5500,
            "total_value": 8000,
            "cash_flow": 1000,
            "created_at": "2023-10-01T12:00:00+00:00",
            "metadata": {"strategy": "mean_reversion"},
        }
        snapshot = PortfolioSnapshot.from_dict(snapshot_data)
        self.assertEqual(snapshot.get_portfolio_id(), "portfolio_1")
        self.assertEqual(snapshot.get_trading_symbol(), "BTC/USDT")
        self.assertEqual(snapshot.get_pending_value(), 5000)
        self.assertEqual(snapshot.unallocated, 2000)
        self.assertEqual(snapshot.net_size, 3000)
        self.assertEqual(snapshot.total_net_gain, 1500)
        self.assertEqual(snapshot.total_revenue, 7000)
        self.assertEqual(snapshot.total_cost, 5500)
        self.assertEqual(snapshot.total_value, 8000)
        self.assertEqual(snapshot.cash_flow, 1000)
        self.assertEqual(
            snapshot.created_at,
            datetime(
                2023,
                10,
                1,
                12,
                0,
                0,
                tzinfo=timezone.utc
            )
        )
        self.assertEqual(
            snapshot.metadata, {"strategy": "mean_reversion"}
        )