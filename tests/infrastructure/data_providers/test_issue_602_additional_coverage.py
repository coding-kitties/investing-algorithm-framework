"""Additional regression coverage for issue #602 / PR #607.

The PR's own unit tests exercise ``OHLCVDataProviderBase.
get_backtest_data`` directly through a stub subclass. These tests add
two more layers of coverage:

1. A full application-level reproduction of the original issue's exact
   scenario (a non-CCXT OHLCV provider, a ``DataSource`` with
   ``window_size``/``warmup_window`` set, run through the vector
   engine) using a synthetic in-memory provider -- no live network
   call required, unlike the issue's ``YahooOHLCVDataProvider`` repro.
2. An edge case the PR's fix did not originally cover: ``backtest_
   end_date`` falls back to the latest available data point when
   omitted, but ``backtest_start_date`` had no matching fallback to
   the earliest available data point -- it silently returned an
   empty DataFrame instead. Fixed to mirror the end_date fallback;
   this test locks that symmetry in.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

import polars as pl

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, DataSource, DataType, PositionSize, Schedule, \
    TimeUnit, Study, Universe, BacktestWindow, BacktestDateRange, \
    BacktestEngine
from investing_algorithm_framework.infrastructure import (
    OHLCVDataProviderBase,
)


def _make_data(rows: int = 400) -> pl.DataFrame:
    """Deterministic daily OHLCV bars, no network access required."""
    return pl.DataFrame(
        {
            "Datetime": [
                datetime(2020, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=i)
                for i in range(rows)
            ],
            "Open": [100.0 + (i % 10) for i in range(rows)],
            "High": [105.0 + (i % 10) for i in range(rows)],
            "Low": [95.0 + (i % 10) for i in range(rows)],
            "Close": [102.0 + (i % 10) for i in range(rows)],
            "Volume": [1_000_000 for _ in range(rows)],
        }
    )


class _SyntheticOHLCVProvider(OHLCVDataProviderBase):
    """A non-CCXT OHLCV provider (same base class as Yahoo/Polygon/
    AlphaVantage) that serves in-memory synthetic data instead of
    calling a real API -- reproduces the issue's provider category
    without a network dependency."""

    market_name = "SYNTH"
    data_provider_identifier = "synthetic_ohlcv"
    timeframe_map = {"1d": "1d"}

    def _download_ohlcv(self, symbol, time_frame, start_date, end_date):
        return _make_data()


class NoOpStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.DAY)

    def generate_signal_series(self, data: Dict[str, Any]):
        return iter(())


class TestIssue602EndToEnd(TestCase):
    """Reproduces the issue #602 script (DataSource with window_size
    on a non-CCXT provider, run through the vector engine) end to end,
    without requiring a live Yahoo Finance connection.
    """

    def setUp(self) -> None:
        import os
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources"
        )

    def test_vector_backtest_with_window_size_on_non_ccxt_provider(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(market="SYNTH", trading_symbol="USD")
        app.add_data_provider(
            data_provider=_SyntheticOHLCVProvider(), priority=1
        )

        strategy = NoOpStrategy(
            algorithm_id="issue_602",
            symbols=["GOOG"],
            data_sources=[
                DataSource(
                    identifier="goog_1d",
                    data_type=DataType.OHLCV,
                    time_frame="1d",
                    market="SYNTH",
                    symbol="GOOG/USD",
                    # <- this is what triggered the TypeError in #602
                    window_size=200,
                    pandas=True,
                )
            ],
            position_sizes=[
                PositionSize(symbol="GOOG", percentage_of_portfolio=99)
            ],
        )

        study = Study(
            universe=Universe(market="SYNTH", trading_symbol="USD"),
            initial_capital=1000,
            backtest_windows=[
                BacktestWindow(
                    train_range=BacktestDateRange(
                        start_date=datetime(2020, 6, 1, tzinfo=timezone.utc),
                        end_date=datetime(2020, 9, 1, tzinfo=timezone.utc),
                    )
                )
            ],
            engines=[BacktestEngine.VECTOR],
        )

        # Previously: TypeError: unsupported operand type(s) for -:
        # 'NoneType' and 'datetime.timedelta'
        backtests = app.run_backtest(strategy=strategy, study=study)

        self.assertEqual(1, backtests.df["algorithm_id"].nunique())


class TestStartDateFallbackAsymmetry(TestCase):
    """A missing *end* date falls back to the latest available data
    point; a missing *start* date must fall back to the earliest
    available data point the same way, rather than silently returning
    an empty DataFrame.
    """

    def test_vectorized_path_missing_start_date_uses_earliest_point(
        self
    ):
        class _Stub(OHLCVDataProviderBase):
            market_name = "STUB"
            data_provider_identifier = "stub_ohlcv"
            timeframe_map = {"1d": "1d"}

            def _download_ohlcv(self, *args, **kwargs):
                raise AssertionError("_download_ohlcv must not be called")

        provider = _Stub(time_frame="1d", window_size=None)
        provider.data = _make_data(rows=10)

        data = provider.get_backtest_data(
            backtest_index_date=None,
            backtest_start_date=None,
            backtest_end_date=datetime(2020, 1, 5, tzinfo=timezone.utc),
        )

        self.assertEqual(5, len(data))
