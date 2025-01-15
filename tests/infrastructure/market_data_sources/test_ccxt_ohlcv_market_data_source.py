import os
from datetime import datetime
from unittest import TestCase, mock

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
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual(200, ccxt_ohlcv_market_data_source.window_size)

    def test_get_market(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("BITVAVO", ccxt_ohlcv_market_data_source.market)

    def test_get_symbol(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("BTC/EUR", ccxt_ohlcv_market_data_source.symbol)

    def test_get_timeframe(self):
        ccxt_ohlcv_market_data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        self.assertEqual("15m", ccxt_ohlcv_market_data_source.get_time_frame())

    @mock.patch('investing_algorithm_framework.infrastructure.services.market_service.ccxt_market_service.CCXTMarketService.get_ohlcv')
    def test_get_data_with_only_window_size(self, mock):
        data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            window_size=200,
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
        )
        mock.return_value = {'key': 'value'}
        data = data_source.get_data()
        self.assertIsNotNone(data)
        self.assertEqual(data_source.window_size, 200)

    @mock.patch('investing_algorithm_framework.infrastructure.services.market_service.ccxt_market_service.CCXTMarketService.get_ohlcv')
    def test_get_data_with_only_start_date(self, mock):
        data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
            window_size=200
        )
        mock.return_value = {'key': 'value'}
        data = data_source.get_data(
            start_date=datetime(2021, 1, 1)
        )
        self.assertIsNotNone(data)

    @mock.patch('investing_algorithm_framework.infrastructure.services.market_service.ccxt_market_service.CCXTMarketService.get_ohlcv')
    def test_get_data_with_only_date_and_end_date(self, mock):
        data_source = CCXTOHLCVMarketDataSource(
            identifier="BTC/EUR",
            time_frame="15m",
            market="BITVAVO",
            symbol="BTC/EUR",
            window_size=200
        )
        mock.return_value = {'key': 'value'}
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2021, 1, 2)
        data = data_source.get_data(
            start_date=start_date,
            end_date=end_date
        )
        self.assertIsNotNone(data)
