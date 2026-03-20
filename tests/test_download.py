import os
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import polars as pl

from investing_algorithm_framework import download


class TestDownload(TestCase):

    @patch("investing_algorithm_framework.infrastructure"
           ".data_providers.ccxt.ccxt")
    def test_download_data_with_already_existing_data(self, mock_ccxt_module):
        """
        Test that download() works when local CSV data already exists.
        Uses test_data/ohlcv CSVs; CCXT is mocked so no network call
        is made (the provider reads from the local file).
        """
        # Mock the exchange so has_data() succeeds without network
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"BTC/EUR": {}}
        mock_exchange.timeframes = {"2h": "2h"}
        mock_exchange_class = MagicMock(return_value=mock_exchange)
        mock_ccxt_module.bitvavo = mock_exchange_class

        storage_path = (
            Path(__file__).parent / "resources" / "test_data" / "ohlcv"
        )
        data = download(
            symbol="BTC/EUR",
            market="BITVAVO",
            data_type="OHLCV",
            time_frame="2h",
            start_date=datetime(2023, 8, 11, 16, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 2, 0, 0, tzinfo=timezone.utc),
            storage_path=str(storage_path)
        )
        self.assertIsNotNone(data)
        self.assertNotEqual(len(data), 0)
