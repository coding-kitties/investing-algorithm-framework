"""Tests for VectorBacktestService pipeline injection (#502 phase 2b).

These verify that strategies declaring ``pipelines = [...]`` receive
the pipeline output in their ``data`` dict before the vectorised
signal generators are invoked. Targeted at ``_inject_pipelines`` —
the helper is a pure static method on the service so we exercise it
directly without spinning up a full backtest.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import polars as pl
import pytest

from investing_algorithm_framework import (
    AverageDollarVolume,
    BacktestDateRange,
    DataSource,
    DataType,
    Pipeline,
    Returns,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import VectorBacktestService


def _ohlcv_polars(closes_volumes):
    rows = []
    for i, (close, volume) in enumerate(closes_volumes):
        rows.append(
            {
                "Datetime": datetime(2024, 1, 1) + timedelta(days=i),
                "Open": close,
                "High": close,
                "Low": close,
                "Close": close,
                "Volume": volume,
            }
        )
    return pl.DataFrame(rows)


class _Screener(Pipeline):
    adv = AverageDollarVolume(window=2)
    momentum = Returns(window=2)
    universe = adv.top(2)


class _StubStrategy:
    """Bare-minimum strategy stand-in (no app wiring)."""

    def __init__(self, data_sources, pipelines=None):
        self.data_sources = data_sources
        self.pipelines = pipelines or []


def _make_data_sources_and_data():
    sources = []
    data = {}
    bars = {
        "AAA/EUR": [(10, 100), (12, 100), (14, 100), (15, 100)],
        "BBB/EUR": [(10, 1), (11, 1), (12, 1), (13, 1)],
        "CCC/EUR": [(10, 200), (11, 200), (13, 200), (14, 200)],
    }
    for symbol, bars_for_symbol in bars.items():
        ds = DataSource(
            data_type="ohlcv",
            market="bitvavo",
            symbol=symbol,
            time_frame="1d",
            identifier=f"{symbol}-ohlcv",
        )
        sources.append(ds)
        data[ds.get_identifier()] = _ohlcv_polars(bars_for_symbol)
    return sources, data


def test_inject_pipelines_no_pipelines_is_noop():
    sources, data = _make_data_sources_and_data()
    strategy = _StubStrategy(data_sources=sources, pipelines=None)
    before = dict(data)

    VectorBacktestService._inject_pipelines(
        strategy=strategy,
        data=data,
        backtest_date_range=BacktestDateRange(
            start_date=datetime(2024, 1, 2),
            end_date=datetime(2024, 1, 4),
        ),
    )
    assert data == before


def test_inject_pipelines_adds_long_frame_keyed_by_class_name():
    sources, data = _make_data_sources_and_data()
    strategy = _StubStrategy(data_sources=sources, pipelines=[_Screener])

    VectorBacktestService._inject_pipelines(
        strategy=strategy,
        data=data,
        backtest_date_range=BacktestDateRange(
            start_date=datetime(2024, 1, 2),
            end_date=datetime(2024, 1, 4),
        ),
    )

    assert "_Screener" in data
    out = data["_Screener"]
    assert isinstance(out, pl.DataFrame)
    # Long format: datetime + symbol + factor columns (universe dropped)
    assert set(out.columns) == {"datetime", "symbol", "adv", "momentum"}
    # Universe restricts to top-2 by ADV every bar; BBB always loses
    # (volume=1 vs 100/200) so it must never appear in the output.
    assert "BBB/EUR" not in out["symbol"].to_list()


def test_inject_pipelines_respects_end_date_no_lookahead():
    sources, data = _make_data_sources_and_data()
    strategy = _StubStrategy(data_sources=sources, pipelines=[_Screener])

    VectorBacktestService._inject_pipelines(
        strategy=strategy,
        data=data,
        backtest_date_range=BacktestDateRange(
            start_date=datetime(2024, 1, 2),
            end_date=datetime(2024, 1, 3),
        ),
    )
    out = data["_Screener"]
    # No bars beyond end_date should leak in.
    max_dt = out["datetime"].max()
    assert max_dt <= datetime(2024, 1, 3)


def test_inject_pipelines_skips_when_no_ohlcv_sources(caplog):
    """A strategy with pipelines but no OHLCV data sources should log
    and skip silently without raising."""
    strategy = _StubStrategy(data_sources=[], pipelines=[_Screener])
    data = {}

    with caplog.at_level(
        "WARNING",
        logger=(
            "investing_algorithm_framework.infrastructure.services."
            "backtesting.vector_backtest_service"
        ),
    ):
        VectorBacktestService._inject_pipelines(
            strategy=strategy,
            data=data,
            backtest_date_range=BacktestDateRange(
                start_date=datetime(2024, 1, 2),
                end_date=datetime(2024, 1, 3),
            ),
        )

    assert "_Screener" not in data
    assert any(
        "no OHLCV data sources" in record.message
        for record in caplog.records
    )


def test_inject_pipelines_re_raises_engine_errors():
    """Pipeline evaluation errors should propagate to the caller so
    backtest authors see a clear failure rather than a silent skip."""

    class _Broken(Pipeline):
        adv = AverageDollarVolume(window=2)
        momentum = Returns(window=2)

    sources, data = _make_data_sources_and_data()
    # Corrupt one of the inputs to force a polars-level error.
    bad_id = sources[0].get_identifier()
    data[bad_id] = pl.DataFrame(
        {"Datetime": [datetime(2024, 1, 1)], "Close": [10.0]}
    )

    strategy = _StubStrategy(data_sources=sources, pipelines=[_Broken])

    with pytest.raises(Exception):
        VectorBacktestService._inject_pipelines(
            strategy=strategy,
            data=data,
            backtest_date_range=BacktestDateRange(
                start_date=datetime(2024, 1, 2),
                end_date=datetime(2024, 1, 4),
            ),
        )


# Suppress the unused import warning — kept for symmetry with other
# vector-backtest tests in the suite.
_ = SimpleNamespace, DataType
