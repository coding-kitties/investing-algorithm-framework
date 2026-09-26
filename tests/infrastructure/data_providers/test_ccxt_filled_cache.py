from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

import polars as pl

from investing_algorithm_framework import CCXTOHLCVDataProvider
from investing_algorithm_framework.infrastructure.services.backtesting \
    .backtest_service import BacktestService
from investing_algorithm_framework.services.data_providers.data import (
    get_missing_timeseries_data_entries,
)


class TestCCXTFilledCache(TestCase):
    def test_full_range_preparation_skips_rolling_window_cache(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        provider = CCXTOHLCVDataProvider(
            symbol="BTC/EUR",
            market="BITVAVO",
            time_frame="15m",
            window_size=2,
        )
        frame = pl.DataFrame({
            "Datetime": [
                start + timedelta(minutes=15 * position)
                for position in range(-2, 5)
            ],
            **{
                column: [float(value) for value in range(7)]
                for column in ("Open", "High", "Low", "Close", "Volume")
            },
        })

        with (
            patch.object(provider, "get_ohlcv", return_value=frame),
            patch.object(provider, "_precompute_sliding_windows") as rolling,
        ):
            provider.prepare_backtest_data_for_access(
                start,
                end,
                access_pattern="full_range",
            )

        rolling.assert_not_called()
        self.assertEqual(provider.data["Datetime"].min(), start - timedelta(
            minutes=30
        ))
        self.assertEqual(provider.window_cache, {})

    def test_initialization_forwards_persistence_only_to_ccxt(self):
        for persist in (False, True):
            with self.subTest(persist=persist):
                service = MagicMock()
                cached_provider = MagicMock(spec=CCXTOHLCVDataProvider)
                custom_provider = MagicMock()
                provider_service = service._data_provider_service
                provider_service.data_provider_index.get_all.return_value = [
                    ("cached", cached_provider), ("custom", custom_provider),
                ]
                date_range = MagicMock()
                data_source = MagicMock()
                data_source.get_identifier.return_value = "test-ohlcv"
                BacktestService.initialize_data_sources_backtest(
                    service, [data_source], date_range,
                    fill_missing_data=True, save_filled_data_points=persist,
                )
                expected = dict(
                    backtest_start_date=date_range.start_date,
                    backtest_end_date=date_range.end_date,
                    fill_missing_data=True, show_progress=False,
                    access_pattern="rolling",
                )
                custom_provider.prepare_backtest_data_for_access \
                    .assert_called_once_with(**expected)
                if persist:
                    expected["save_filled_data_points"] = True
                cached_provider.prepare_backtest_data_for_access \
                    .assert_called_once_with(**expected)

    def test_filled_cache_is_opt_in_and_preserves_other_windows(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        frame = pl.DataFrame({
            "Datetime": [
                start + timedelta(minutes=15 * position)
                for position in (-1, 0, 2, 3, 4, 5)
            ],
            **{
                column: [float(value) for value in range(100, 106)]
                for column in ("Open", "High", "Low", "Close", "Volume")
            },
        })
        for persist, fill in ((False, True), (True, True), (True, False)):
            with self.subTest(persist=persist, fill=fill):
                with TemporaryDirectory() as directory:
                    options = dict(
                        symbol="BTC/EUR", market="BITVAVO", time_frame="15m",
                        window_size=2, storage_directory=directory,
                    )
                    provider = CCXTOHLCVDataProvider(**options)
                    provider._write_canonical_file(
                        directory, "BTC/EUR", "BITVAVO", "15m", frame,
                    )
                    original = Path(provider.data_file_path).read_bytes()
                    for run_number in (1, 2):
                        provider = CCXTOHLCVDataProvider(**options)
                        with patch.object(
                            provider, "get_ohlcv",
                            side_effect=AssertionError("Unexpected download"),
                        ):
                            provider.prepare_backtest_data(
                                start + timedelta(minutes=30), end,
                                fill_missing_data=fill,
                                save_filled_data_points=persist,
                            )
                        cached = provider._read_canonical_file(
                            directory, "BTC/EUR", "BITVAVO", "15m",
                        )
                        gaps = get_missing_timeseries_data_entries(
                            cached, start=start, end=end, freq="15min",
                        )
                        self.assertEqual(
                            len(gaps), 0 if persist and fill else 1
                        )
                        self.assertEqual(
                            len(cached), 7 if persist and fill else 6
                        )
                        original_rows = cached.filter(
                            pl.col("Datetime") != start + timedelta(minutes=15)
                        )
                        self.assertEqual(original_rows.rows(), frame.rows())
                        self.assertEqual(
                            len(provider.data), 5 if fill else 4,
                        )
                        if not (persist and fill):
                            self.assertEqual(
                                Path(provider.data_file_path).read_bytes(),
                                original,
                            )
