from unittest import TestCase
from datetime import datetime, timedelta
from investing_algorithm_framework.infrastructure import \
    CSVOHLCVMarketDataSource
import os


class Test(TestCase):

    def test_right_columns(self):
        resource_dir = os.path.abspath(
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
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            identifier="BTC",
            market="BITVAVO",
            symbol="BTC/EUR",
            timeframe="15m",
            start_date_func=lambda: datetime.utcnow() - timedelta(days=17),
            csv_file_path=f"{resource_dir}/"
                          "market_data_sources/"
                          "OHLCV_BTC-EUR_15m_2021-05-17:00:00_2021-06-26:00:00.csv"
        )

        self.assertEqual(
            csv_ohlcv_market_data_source.csv_file_path,
            f"{resource_dir}/"
            "market_data_sources/"
            "OHLCV_BTC-EUR_15m_2021-05-17:00:00_2021-06-26:00:00.csv"
        )
        self.assertEqual(
            csv_ohlcv_market_data_source.identifier,
            "BTC"
        )
        self.assertEqual(
            csv_ohlcv_market_data_source.market,
            "BITVAVO"
        )
        self.assertEqual(
            csv_ohlcv_market_data_source.symbol,
            "BTC/EUR"
        )
        self.assertEqual(
            csv_ohlcv_market_data_source.start_date.replace(microsecond=0),
            (datetime.utcnow() - timedelta(days=17)).replace(microsecond=0)
        )
