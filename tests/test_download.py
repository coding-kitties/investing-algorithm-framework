from pathlib import Path
from unittest import TestCase
from datetime import datetime, timezone

from investing_algorithm_framework import download



class TestDownload(TestCase):

    def test_download_data_with_already_existing_data(self):
        storage_path = Path(__file__).parent / "resources" / "data"
        data = download(
            symbol="BTC/EUR",
            market="BITVAVO",
            data_type="OHLCV",
            time_frame="2h",
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            storage_path=str(storage_path)
        )
        self.assertIsNotNone(data)
        self.assertNotEqual(len(data), 0)
