from unittest import TestCase
from datetime import datetime, timedelta
from investing_algorithm_framework.infrastructure import CsvOHLCVMarketDataSource


class Test(TestCase):


    def test_right_columns(self):
        csv_ohlcv_market_data_source = CsvOHLCVMarketDataSource(
            identifier="BTC",
            market="BITVAVO",
            symbol="BTC/EUR",
            timeframe="15m",
            start_date_func=lambda: datetime.utcnow() - timedelta(days=17),
            csv_file_path="../../../tests/resources/"
                          "market_data_sources/"
                          "OHLCV_BTC-EUR_2h_2023-08-07:00:00_2023-12-02:00:00.csv"
        )

        self.assertEqual(
            csv_ohlcv_market_data_source.csv_file_path,
            "../../../tests/resources/"
            "market_data_sources/"
            "OHLCV_BTC-EUR_2h_2023-08-07:00:00_2023-12-02:00:00.csv"
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
