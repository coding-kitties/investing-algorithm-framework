from datetime import datetime, timezone, date
from unittest import TestCase

from investing_algorithm_framework.domain import PortfolioSnapshot
from investing_algorithm_framework.services import get_mean_daily_return


class TestVolatilityMetrics(TestCase):

    def test_mean_daily_return_calculation(self):
        total_values = [
            100000,
            101154,
            102949,
            101090,
            99487,
            99936,
            101026,
            103974,
            105320,
            105384,
            103333,
            106602,
            108397,
            107243,
            107373,
            106666,
            107756,
            107307,
            109615,
            108846,
            108589,
            107372
        ]

        dates = [
            date(year=2010, month=9, day=10),
            date(year=2010, month=9, day=13),
            date(year=2010, month=9, day=14),
            date(year=2010, month=9, day=15),
            date(year=2010, month=9, day=16),
            date(year=2010, month=9, day=17),
            date(year=2010, month=9, day=20),
            date(year=2010, month=9, day=21),
            date(year=2010, month=9, day=22),
            date(year=2010, month=9, day=23),
            date(year=2010, month=9, day=24),
            date(year=2010, month=9, day=27),
            date(year=2010, month=9, day=28),
            date(year=2010, month=9, day=29),
            date(year=2010, month=9, day=30),
            date(year=2010, month=10, day=1),
            date(year=2010, month=10, day=4),
            date(year=2010, month=10, day=5),
            date(year=2010, month=10, day=6),
            date(year=2010, month=10, day=7),
            date(year=2010, month=10, day=8),
            date(year=2010, month=10, day=12)
        ]

        snapshots = [
            PortfolioSnapshot(
                portfolio_id="test_portfolio",
                total_value=val,
                created_at=datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
            for d, val in zip(dates, total_values)
        ]

        mean_daily_return = get_mean_daily_return(snapshots)
        self.assertAlmostEqual(mean_daily_return, 0.002225, places=3)
