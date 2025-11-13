from unittest import TestCase
from datetime import datetime, timezone, timedelta, date
from investing_algorithm_framework.services import get_annual_volatility
from investing_algorithm_framework.domain import PortfolioSnapshot


class TestVolatilityMetrics(TestCase):

    def test_volatility_metrics_calculation(self):
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
        print(len(dates))
        print(len(total_values))

        snapshots = [
            PortfolioSnapshot(
                portfolio_id="test_portfolio",
                total_value=val,
                created_at=datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
            for d, val in zip(dates, total_values)
        ]

        annual_volatility = get_annual_volatility(snapshots, trading_days_per_year=252)

        # Expected annual volatility = 0.01502 * sqrt(252) ≈ 0.2383 from the
        # book trading systems and methods by perry j. kaufman page 42
        expected = 0.01502 * (252 ** 0.5)
        self.assertAlmostEqual(annual_volatility, expected, places=2)
