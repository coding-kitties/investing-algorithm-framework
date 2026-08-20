"""Tests for #503 phase 3b/3c/3d — live-mode pipeline hardening.

Covers:
  * Envelope validation (max 50 symbols, daily-or-coarser timeframes)
  * Universe-refresh cadence cache
  * Per-pipeline error resilience in non-backtest environments
"""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase

from investing_algorithm_framework import (
    DataSource, DataType, OperationalException,
)
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.domain import TimeFrame, Environment
from investing_algorithm_framework.domain.pipeline.pipeline import Pipeline
from investing_algorithm_framework.domain.pipeline.factors.builtin import (
    SMA,
)


# ----------------------------------------------------------------- #
# Fixtures
# ----------------------------------------------------------------- #
def _ds(symbol, time_frame=TimeFrame.ONE_DAY, warmup_window=10):
    return DataSource(
        symbol=symbol,
        data_type=DataType.OHLCV,
        time_frame=time_frame,
        market="bitvavo",
        warmup_window=warmup_window,
    )


class _DailyPipeline(Pipeline):
    sma = SMA(window=5)


class _CadencePipeline(Pipeline):
    sma = SMA(window=5)
    refresh_universe_every = timedelta(days=1)


def _strategy(strategy_id, data_sources, pipelines):
    """Minimal stub satisfying the attributes ``_run_pipelines`` and
    ``_validate_live_envelope`` read."""
    return SimpleNamespace(
        strategy_id=strategy_id,
        data_sources=data_sources,
        pipelines=pipelines,
    )


def _eventloop(env=Environment.DEV):
    """Construct an :class:`EventLoopService` with stub services. The
    helper methods under test only need ``configuration_service`` to
    return ``{"environment": env}``, the rest can stay ``None``."""
    cfg = SimpleNamespace(
        get_config=lambda: {
            "environment": env.value,
            "ENVIRONMENT": env.value,
        },
    )
    return EventLoopService(
        context=None,
        order_service=None,
        trade_service=None,
        portfolio_service=None,
        configuration_service=cfg,
        data_provider_service=None,
        portfolio_snapshot_service=None,
    )


# ----------------------------------------------------------------- #
# 3b: envelope validation
# ----------------------------------------------------------------- #
class TestLiveEnvelopeValidation(TestCase):
    def test_sub_daily_with_pipeline_raises(self):
        loop = _eventloop()
        strat = _strategy(
            "s1",
            [_ds("BTC/EUR", time_frame=TimeFrame.ONE_HOUR,
                 warmup_window=200)],
            [_DailyPipeline],
        )
        with self.assertRaises(OperationalException) as cm:
            loop._validate_live_envelope([strat])
        self.assertIn("sub-daily", str(cm.exception))

    def test_too_many_symbols_raises(self):
        loop = _eventloop()
        sources = [
            _ds(f"S{i}/EUR", time_frame=TimeFrame.ONE_DAY)
            for i in range(51)
        ]
        strat = _strategy("s1", sources, [_DailyPipeline])
        with self.assertRaises(OperationalException) as cm:
            loop._validate_live_envelope([strat])
        self.assertIn("exceeds the v1 live cap", str(cm.exception))

    def test_daily_under_cap_passes(self):
        loop = _eventloop()
        sources = [
            _ds(f"S{i}/EUR", time_frame=TimeFrame.ONE_DAY)
            for i in range(50)
        ]
        strat = _strategy("s1", sources, [_DailyPipeline])
        loop._validate_live_envelope([strat])  # no raise

    def test_no_pipelines_skips_validation(self):
        """Strategies without pipelines are unaffected — sub-daily +
        many symbols must not raise."""
        loop = _eventloop()
        sources = [
            _ds(f"S{i}/EUR", time_frame=TimeFrame.ONE_HOUR)
            for i in range(100)
        ]
        strat = _strategy("s1", sources, [])
        loop._validate_live_envelope([strat])  # no raise

    def test_backtest_mode_skips_validation(self):
        """``_maybe_validate_live_envelope`` is a no-op for BACKTEST
        even when the strategy violates the live envelope."""
        loop = _eventloop(env=Environment.BACKTEST)
        strat = _strategy(
            "s1",
            [_ds("BTC/EUR", time_frame=TimeFrame.ONE_HOUR)],
            [_DailyPipeline],
        )
        # Would raise via _validate_live_envelope, but
        # _maybe_validate_live_envelope short-circuits in backtest.
        loop._maybe_validate_live_envelope(
            [strat], Environment.BACKTEST.value,
        )

    def test_validation_runs_only_once(self):
        loop = _eventloop()
        sources = [_ds("BTC/EUR", time_frame=TimeFrame.ONE_DAY)]
        strat = _strategy("s1", sources, [_DailyPipeline])
        loop._maybe_validate_live_envelope(
            [strat], Environment.DEV.value,
        )
        self.assertTrue(loop._pipelines_live_validated)
        # Even if we mutate the strategy to violate the envelope,
        # subsequent calls don't re-run validation.
        strat.data_sources = [
            _ds("BTC/EUR", time_frame=TimeFrame.ONE_HOUR),
        ]
        loop._maybe_validate_live_envelope(
            [strat], Environment.DEV.value,
        )  # no raise


# ----------------------------------------------------------------- #
# 3c: refresh_universe_every cache (moved to EvaluatePipelinesPhase
# in v9.0; the eventloop no longer owns the cache).
# ----------------------------------------------------------------- #
class TestUniverseRefreshCache(TestCase):
    def _phase(self):
        from investing_algorithm_framework.services.strategy_phases \
            .evaluate_pipelines import EvaluatePipelinesPhase
        return EvaluatePipelinesPhase

    def test_no_attribute_returns_none(self):
        phase = self._phase()
        result = phase._filter_for_universe_cache(
            strategy=SimpleNamespace(_pipeline_universe_cache={}),
            pipeline_cls=_DailyPipeline,  # no refresh_universe_every
            symbol_to_identifier={"A": "id_a"},
            as_of=datetime(2024, 1, 1),
        )
        self.assertIsNone(result)

    def test_no_cache_entry_returns_none(self):
        phase = self._phase()
        result = phase._filter_for_universe_cache(
            strategy=SimpleNamespace(_pipeline_universe_cache={}),
            pipeline_cls=_CadencePipeline,
            symbol_to_identifier={"A": "id_a"},
            as_of=datetime(2024, 1, 1),
        )
        self.assertIsNone(result)

    def test_cache_hit_within_cadence_restricts_symbols(self):
        phase = self._phase()
        strat = SimpleNamespace(
            _pipeline_universe_cache={
                _CadencePipeline: (
                    datetime(2024, 1, 1),
                    frozenset({"A", "B"}),
                ),
            },
        )
        result = phase._filter_for_universe_cache(
            strategy=strat,
            pipeline_cls=_CadencePipeline,
            symbol_to_identifier={"A": "id_a", "B": "id_b", "C": "id_c"},
            as_of=datetime(2024, 1, 1, 12),  # 12h later, < 1d cadence
        )
        self.assertEqual(result, {"A": "id_a", "B": "id_b"})

    def test_cache_miss_after_cadence_returns_none(self):
        phase = self._phase()
        strat = SimpleNamespace(
            _pipeline_universe_cache={
                _CadencePipeline: (
                    datetime(2024, 1, 1),
                    frozenset({"A"}),
                ),
            },
        )
        result = phase._filter_for_universe_cache(
            strategy=strat,
            pipeline_cls=_CadencePipeline,
            symbol_to_identifier={"A": "id_a"},
            as_of=datetime(2024, 1, 2, 1),  # > 1d after cache
        )
        self.assertIsNone(result)


# ----------------------------------------------------------------- #
# 3d: per-pipeline resilience (now driven through EvaluatePipelinesPhase).
# ----------------------------------------------------------------- #
class _BoomEngine:
    """Stand-in pipeline engine that always raises."""

    def evaluate(self, **kwargs):
        raise RuntimeError("boom")

    @staticmethod
    def _empty_output(pipeline_cls):
        import polars as pl
        return pl.DataFrame(
            schema={"symbol": pl.Utf8, "sma": pl.Float64},
        )


class _PhaseStateStub:
    """Minimal PhaseState surface the phase reads from."""

    def __init__(self, strategy, data, as_of, is_backtest):
        self.strategy = strategy
        self.data = data
        self.current_datetime = as_of
        # context.config[ENVIRONMENT] is what the phase actually reads
        env = (
            Environment.BACKTEST.value
            if is_backtest else Environment.DEV.value
        )
        self.context = SimpleNamespace(config={"ENVIRONMENT": env})
        self.traces = []

    def trace(self, tag, payload):
        self.traces.append((tag, payload))


class TestEvaluatePipelinesPhaseResilience(TestCase):
    def _setup(self, env):
        from investing_algorithm_framework.services.strategy_phases \
            .evaluate_pipelines import EvaluatePipelinesPhase
        phase = EvaluatePipelinesPhase(engine=_BoomEngine())
        strat = _strategy(
            "s1",
            [_ds("BTC/EUR", time_frame=TimeFrame.ONE_DAY)],
            [_DailyPipeline],
        )
        strat._pipeline_universe_cache = {}
        state = _PhaseStateStub(
            strategy=strat,
            data={ds.get_identifier(): None for ds in strat.data_sources},
            as_of=datetime(2024, 1, 1),
            is_backtest=Environment.BACKTEST.equals(env),
        )
        return phase, state

    def test_live_mode_swallows_pipeline_error(self):
        phase, state = self._setup(Environment.DEV)
        logger_name = (
            "investing_algorithm_framework.services.strategy_phases"
            ".evaluate_pipelines"
        )
        # Failure is expected here — assertLogs both captures the
        # traceback (keeping it out of the test console) and confirms
        # it was actually logged.
        with self.assertLogs(logger_name, level=logging.ERROR):
            phase.run(state)
        self.assertIn("_DailyPipeline", state.data)
        # Empty output — schema preserved, no rows.
        self.assertEqual(state.data["_DailyPipeline"].height, 0)

    def test_backtest_mode_reraises_pipeline_error(self):
        phase, state = self._setup(Environment.BACKTEST)
        logger_name = (
            "investing_algorithm_framework.services.strategy_phases"
            ".evaluate_pipelines"
        )
        with self.assertLogs(logger_name, level=logging.ERROR):
            with self.assertRaises(RuntimeError):
                phase.run(state)
