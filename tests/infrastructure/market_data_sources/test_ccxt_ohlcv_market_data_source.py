import os
from datetime import datetime, timedelta
from unittest import TestCase

from investing_algorithm_framework.infrastructure import \
    CCXTOHLCVMarketDataSource


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

    def test_window_size(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual(200, ccxt_ohlcv_market_data_source.window_size)

    def test_start_date(self):
        current_datetime = datetime.utcnow()
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual(
            (current_datetime - timedelta(minutes=200 * 15))
            .strftime("%Y-%m-%d %H:%M"),
            ccxt_ohlcv_market_data_source.start_date.strftime("%Y-%m-%d %H:%M")
        )

    def test_end_date(self):
        current_datetime = datetime.utcnow()
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual(
            current_datetime.strftime("%Y-%m-%d %H:%M"),
            ccxt_ohlcv_market_data_source.end_date.strftime("%Y-%m-%d %H:%M")
        )

    def test_get_market(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("BITVAVO", ccxt_ohlcv_market_data_source.market)

    def test_get_symbol(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("BTC/EUR", ccxt_ohlcv_market_data_source.symbol)

    def test_get_timeframe(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            timeframe="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("15m", ccxt_ohlcv_market_data_source.timeframe)
