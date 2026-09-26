from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

import polars as pl

from investing_algorithm_framework.domain import (
    BacktestDateRange,
    DataSource,
)
from investing_algorithm_framework.infrastructure import (
    CCXTOHLCVDataProvider,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .backtest_service import BacktestService
from investing_algorithm_framework.services import DataProviderService
from investing_algorithm_framework.services.data_providers \
    .prepared_market_data import PreparedMarketDataContext


class TestPreparedMarketDataContext(TestCase):
    def setUp(self):
        self.start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=1)
        self.date_range = BacktestDateRange(self.start, self.end)
        self.data_source = DataSource(
            identifier="btc",
            data_type="OHLCV",
            symbol="BTC/EUR",
            market="BITVAVO",
            time_frame="15m",
            warmup_window=2,
        )

    def test_reuses_opted_in_prepared_provider_after_index_reset(self):
        base_provider = CCXTOHLCVDataProvider(
            storage_directory="/tmp/market-data",
        )
        prepared_provider = base_provider.copy(self.data_source)
        prepared_provider.data = pl.DataFrame({
            "Datetime": [self.start, self.end],
            "Close": [1.0, 2.0],
        })
        prepared_window = prepared_provider.data.head(1)
        prepared_provider.window_cache = {
            self.start: prepared_window,
        }
        context = PreparedMarketDataContext(max_bytes=1024 * 1024)
        provider_service = DataProviderService()
        provider_service.prepared_market_data_context = context
        provider_service.data_provider_index.add(base_provider)
        service = object.__new__(BacktestService)
        service._data_provider_service = provider_service

        with (
            patch.object(base_provider, "has_data", return_value=True),
            patch.object(
                base_provider, "copy", return_value=prepared_provider
            ) as copy_provider,
            patch.object(
                prepared_provider, "prepare_backtest_data_for_access"
            ) as prepare,
        ):
            service.initialize_data_sources_backtest(
                [self.data_source],
                self.date_range,
                access_pattern="rolling",
            )
            provider_service.reset()
            provider_service.data_provider_index.add(base_provider)
            service.initialize_data_sources_backtest(
                [self.data_source],
                self.date_range,
                access_pattern="rolling",
            )

        copy_provider.assert_called_once_with(self.data_source)
        prepare.assert_called_once()
        rebound_provider = provider_service.data_provider_index.get(
            self.data_source
        )
        self.assertIsNot(rebound_provider, prepared_provider)
        self.assertIs(rebound_provider.data, prepared_provider.data)
        self.assertIsNot(
            rebound_provider.window_cache,
            prepared_provider.window_cache,
        )
        self.assertIs(
            rebound_provider.window_cache[self.start],
            prepared_window,
        )
        self.assertEqual(context.stats.builds, 1)
        self.assertEqual(context.stats.hits, 1)
        self.assertEqual(context.stats.misses, 1)

    def test_context_evicts_least_recently_used_entry(self):
        context = PreparedMarketDataContext(max_bytes=16)
        provider_one = type("Provider", (), {
            "data": type("Data", (), {"estimated_size": lambda self: 10})(),
            "window_cache": {},
        })()
        provider_two = type("Provider", (), {
            "data": type("Data", (), {"estimated_size": lambda self: 10})(),
            "window_cache": {},
        })()

        context.put(("one",), provider_one)
        context.put(("two",), provider_two)

        self.assertIsNone(context.get(("one",)))
        self.assertIs(context.get(("two",)), provider_two)
        self.assertEqual(context.stats.evictions, 1)
        self.assertLessEqual(context.stats.resident_bytes, 16)

    def test_context_records_preparation_stage_statistics(self):
        context = PreparedMarketDataContext(max_bytes=16)

        context.record_registration(1.25)
        context.record_registration(0.25)
        context.record_preparation(2.5, rolling_cache_built=True)
        context.record_preparation(0.5, rolling_cache_built=False)

        self.assertEqual(context.stats.registration_seconds, 1.5)
        self.assertEqual(context.stats.preparation_seconds, 3.0)
        self.assertEqual(context.stats.rolling_cache_builds, 1)
