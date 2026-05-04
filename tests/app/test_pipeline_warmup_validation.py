"""Phase 3 (#503): warmup_window validation for pipelines.

When a strategy declares ``pipelines = [...]`` the framework now
verifies at strategy construction time that every OHLCV data source
has a ``warmup_window`` >= the pipeline's longest factor window.
Without this check a live strategy starts silently emitting NaN
columns until enough bars accrue.
"""
from unittest import TestCase

from investing_algorithm_framework import (
    DataSource,
    DataType,
    Pipeline,
    Returns,
    SMA,
    TimeFrame,
    TimeUnit,
    TradingStrategy,
)
from investing_algorithm_framework.domain import OperationalException


class _ShortPipeline(Pipeline):
    momentum = Returns(window=5)


class _LongPipeline(Pipeline):
    sma = SMA(window=200)


class _PipelineStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]

    def generate_buy_signals(self, data):  # pragma: no cover - not exercised
        return {}

    def generate_sell_signals(self, data):  # pragma: no cover - not exercised
        return {}


def _ds(warmup_window=None):
    kwargs = dict(
        symbol="BTC/EUR",
        data_type=DataType.OHLCV,
        time_frame=TimeFrame.ONE_HOUR,
        market="BITVAVO",
    )
    if warmup_window is not None:
        kwargs["warmup_window"] = warmup_window
    return DataSource(**kwargs)


class TestPipelineWarmupValidation(TestCase):
    def test_sufficient_warmup_window_passes(self):
        strategy = _PipelineStrategy(
            data_sources=[_ds(warmup_window=10)],
            decorated=None,
        )
        strategy.pipelines = [_ShortPipeline]
        # Re-init to trigger validation with pipelines set.
        strategy = _PipelineStrategy(
            data_sources=[_ds(warmup_window=10)],
        )
        # Class-level pipelines = [] by default; explicitly set then
        # reconstruct via subclass.

        class _Strat(_PipelineStrategy):
            pipelines = [_ShortPipeline]

        instance = _Strat(data_sources=[_ds(warmup_window=10)])
        self.assertEqual(instance.pipelines, [_ShortPipeline])

    def test_insufficient_warmup_window_raises(self):
        class _Strat(_PipelineStrategy):
            pipelines = [_LongPipeline]

        with self.assertRaises(OperationalException) as cm:
            _Strat(data_sources=[_ds(warmup_window=50)])

        msg = str(cm.exception)
        self.assertIn("_LongPipeline", msg)
        self.assertIn("200", msg)
        self.assertIn("warmup_window", msg)

    def test_unset_warmup_window_raises(self):
        class _Strat(_PipelineStrategy):
            pipelines = [_ShortPipeline]

        with self.assertRaises(OperationalException) as cm:
            _Strat(data_sources=[_ds()])

        msg = str(cm.exception)
        self.assertIn("unset", msg)

    def test_no_ohlcv_data_sources_raises(self):
        class _Strat(_PipelineStrategy):
            pipelines = [_ShortPipeline]

        with self.assertRaises(OperationalException) as cm:
            _Strat(data_sources=[])

        msg = str(cm.exception)
        self.assertIn("no OHLCV data sources", msg)

    def test_no_pipelines_skips_validation(self):
        """Strategies that don't declare pipelines pay zero cost — even
        a missing warmup_window must not raise."""
        instance = _PipelineStrategy(data_sources=[_ds()])
        self.assertEqual(instance.pipelines, [])

    def test_multiple_pipelines_uses_max_window(self):
        class _Strat(_PipelineStrategy):
            pipelines = [_ShortPipeline, _LongPipeline]

        # warmup of 199 satisfies _ShortPipeline (5) but not
        # _LongPipeline (200). The error must mention _LongPipeline.
        with self.assertRaises(OperationalException) as cm:
            _Strat(data_sources=[_ds(warmup_window=199)])
        msg = str(cm.exception)
        self.assertIn("_LongPipeline", msg)
