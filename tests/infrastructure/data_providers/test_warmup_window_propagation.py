"""Regression tests for issue #379.

Ensures `DataSource.warmup_window` propagates to the CCXT
(and other OHLCV) data providers as `window_size`, including
backward-compatibility with the deprecated `window_size=` alias on
``DataSource``.
"""
import warnings
from unittest import TestCase

from investing_algorithm_framework.domain.models.data.data_source import \
    DataSource
from investing_algorithm_framework.infrastructure.data_providers.ccxt import (
    CCXTOHLCVDataProvider,
)


class TestWarmupWindowPropagation(TestCase):
    """Regression tests for #379."""

    def _data_source(self, **kwargs) -> DataSource:
        defaults = dict(
            symbol="BTC/EUR",
            data_type="ohlcv",
            market="BITVAVO",
            time_frame="1h",
        )
        defaults.update(kwargs)
        return DataSource(**defaults)

    def test_warmup_window_propagates_to_ccxt_provider(self):
        """warmup_window on the DataSource ends up as window_size on
        the copied CCXT data provider (#379)."""
        data_source = self._data_source(warmup_window=200)

        provider = CCXTOHLCVDataProvider().copy(data_source)

        self.assertEqual(provider.window_size, 200)

    def test_legacy_window_size_alias_still_propagates(self):
        """The deprecated DataSource(window_size=...) alias still
        propagates to the CCXT provider, while emitting a
        DeprecationWarning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data_source = self._data_source(window_size=150)

        self.assertTrue(
            any(issubclass(w.category, DeprecationWarning) for w in caught),
            "Using DataSource(window_size=...) should emit "
            "a DeprecationWarning",
        )

        provider = CCXTOHLCVDataProvider().copy(data_source)

        self.assertEqual(provider.window_size, 150)

    def test_warmup_window_takes_precedence_over_legacy_alias(self):
        """If both warmup_window and the deprecated window_size are set,
        warmup_window wins on both the DataSource and the provider."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            data_source = self._data_source(
                warmup_window=300, window_size=100
            )

        self.assertEqual(data_source.warmup_window, 300)
        self.assertEqual(data_source.window_size, 300)

        provider = CCXTOHLCVDataProvider().copy(data_source)
        self.assertEqual(provider.window_size, 300)

    def test_no_warmup_window_set_yields_none(self):
        """When neither warmup_window nor window_size is set on the
        DataSource, the provider's window_size is None."""
        data_source = self._data_source()

        provider = CCXTOHLCVDataProvider().copy(data_source)

        self.assertIsNone(provider.window_size)

    def test_data_source_post_init_syncs_warmup_to_window_size(self):
        """DataSource exposes both attributes in sync for backward
        compatibility (consumers reading either still work)."""
        data_source = self._data_source(warmup_window=250)

        self.assertEqual(data_source.warmup_window, 250)
        self.assertEqual(data_source.window_size, 250)
