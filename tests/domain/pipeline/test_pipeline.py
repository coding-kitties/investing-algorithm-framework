"""Unit tests for the Pipeline base class introspection.

See ``investing_algorithm_framework/domain/pipeline/pipeline.py`` and
``docs/design/pipeline-api.md`` (Phase 1, #501).
"""
from __future__ import annotations

import pytest

from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
    SMA,
)


class _Screener(Pipeline):
    dollar_volume = AverageDollarVolume(window=5)
    momentum = Returns(window=3)
    universe = dollar_volume.top(2)
    alpha = momentum.rank(mask=universe)


def test_pipeline_collects_columns_excluding_universe():
    cols = _Screener.get_columns()
    assert list(cols.keys()) == ["dollar_volume", "momentum", "alpha"]
    assert _Screener.get_universe() is _Screener.universe


def test_pipeline_required_columns_union():
    required = _Screener.required_columns()
    # AverageDollarVolume needs close+volume, Returns needs close
    assert "close" in required
    assert "volume" in required


def test_pipeline_required_window_is_max():
    assert _Screener.required_window() == 5


def test_pipeline_name_defaults_to_class_name():
    assert _Screener.name() == "_Screener"


def test_pipeline_with_no_columns_raises():
    with pytest.raises(TypeError, match="declares no factor columns"):
        class _Empty(Pipeline):
            pass


def test_pipeline_universe_must_be_filter():
    with pytest.raises(TypeError, match="must be a Filter"):
        class _BadUniverse(Pipeline):
            momentum = Returns(window=3)
            # Returns is a Factor, not a Filter
            universe = momentum


def test_pipeline_inheritance_collects_parent_columns():
    class _Child(_Screener):
        sma = SMA(window=4)

    cols = _Child.get_columns()
    # Child columns + parent columns
    assert "sma" in cols
    assert "dollar_volume" in cols
    assert "momentum" in cols
    assert "alpha" in cols
