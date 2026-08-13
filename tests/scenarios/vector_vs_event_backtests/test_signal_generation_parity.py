"""
Detailed vector-vs-event signal parity check on a fixed, real
BTC/EUR dataset.

This module deliberately separates two very different questions that
"do vector and event backtests agree?" conflates:

1. **Signal-generation parity** (:class:`TestSignalGenerationParity`)
   — with the *engines* removed from the picture entirely, do the
   two signal-generation code paths a strategy implements
   (``generate_signals`` for event mode, ``generate_signal_series``
   for vector mode) compute the *same* boolean entry/exit values from
   the *same* underlying OHLCV data? This isolates a genuine,
   documented limitation: the vector engine computes indicators
   **once**, in a growing batch, over the whole backtest window; the
   event engine recomputes indicators **fresh, on a sliding window**,
   at every tick (see ``OHLCVDataProvider.get_backtest_data`` /
   ``DataSource.create_start_date_data``). For a long-period
   indicator (EMA-200) that needs many bars to converge, these two
   feeding strategies can disagree even though neither is "buggy".

2. **Engine-level trade parity**
   (:class:`TestEngineLevelTradeParity`) — running the *same*
   strategy through ``app.run_backtest`` (event) and
   ``app.run_vector_backtest`` (vector) end-to-end on the same fixed
   CSV dataset and date range, do the resulting trades line up
   (count, timing, direction)? Given (1), exact equality is not
   guaranteed — this asserts the two stay within a small, documented
   tolerance instead of silently diverging.

3. **The fix** (:class:`TestEngineParityWithRecommendedWarmup`) —
   doubling ``warmup_window`` relative to the strategy's slowest
   indicator period gives both engines enough history to converge
   EMA-200 to the same steady state, closing the gap almost entirely:
   verified 18/22 trades (1x warmup) -> 19/19 identical trades (2x
   warmup) on this dataset. This is the concrete, actionable
   recommendation backing
   ``docs/architecture/backtest/vector-vs-event-engine-parity.md``.

Both classes use the same fixed, real BTC/EUR (BITVAVO, 2h) CSV file
already used by the rest of the event-backtest test suite, so results
are reproducible and require no network access.
"""
import dataclasses
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import (
    create_app, BacktestDateRange, RESOURCE_DIRECTORY, CSVOHLCVDataProvider,
    SnapshotInterval,
)
from tests.resources.strategies_for_testing.strategy_v1 import (
    CrossOverStrategyV1,
)

RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"
CSV_PATH = (
    RESOURCES_DIR / "test_data" / "ohlcv"
    / "OHLCV_BTC-EUR_BITVAVO_2h_2021-09-26-08-00_2023-12-02-00-00.csv"
)

# Matches the validated real-data window used across the event
# backtest scenario suite (see repo memory / other event_backtests/*).
END_DATE = datetime(2023, 12, 2, tzinfo=timezone.utc)

WARMUP_BARS = 200  # CrossOverStrategyV1.trend (the slow trend EMA)
BAR_MINUTES = 120  # "2h" timeframe

# Test every Nth bar (rather than every bar) across the ~2-year CSV so
# Part A covers multiple market regimes (bull/bear/sideways) cheaply —
# each sample only recomputes indicators over a bounded WARMUP_BARS
# sliding window, so cost per sample is constant regardless of how
# deep into the file it is.
FULL_HISTORY_SAMPLE_STRIDE = 4


def _load_ohlcv_csv(path):
    df = pd.read_csv(path)
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
    return df.set_index("Datetime").sort_index()


def _match_trades_by_open_time(a_trades, b_trades, tolerance):
    """Greedily pair each trade in ``a_trades`` with its nearest (by
    ``opened_at``) unmatched trade in ``b_trades`` within
    ``tolerance``.

    Positional (chronological-index) pairing breaks down the moment
    one engine fires a single extra/missing signal, since every
    later trade then shifts by one position. Nearest-neighbour
    matching by timestamp is robust to that.

    Returns:
        tuple: ``(matched_pairs, unmatched_a, unmatched_b)`` where
            ``matched_pairs`` is a list of ``(a, b)`` tuples.
    """
    remaining_b = list(b_trades)
    matched_pairs = []
    unmatched_a = []
    for ta in a_trades:
        best, best_delta = None, None
        for tb in remaining_b:
            delta = abs(ta.opened_at - tb.opened_at)
            if delta <= tolerance and (
                best_delta is None or delta < best_delta
            ):
                best, best_delta = tb, delta
        if best is not None:
            matched_pairs.append((ta, best))
            remaining_b.remove(best)
        else:
            unmatched_a.append(ta)
    return matched_pairs, unmatched_a, remaining_b


class TestSignalGenerationParity(TestCase):
    """Isolate signal-generation logic from engine execution details.

    See module docstring for the full rationale. In short: the vector
    engine primes indicators with a single batch computation over the
    whole available history; the event engine recomputes indicators
    fresh every tick over a *sliding* ``WARMUP_BARS``-bar window
    ending at that tick. Both use the same warmup *size*, but the
    vector engine's batch keeps accumulating history as the window
    progresses while the event engine's slice always forgets anything
    older than ``WARMUP_BARS`` bars back.

    Sampled every ``FULL_HISTORY_SAMPLE_STRIDE``-th bar across the
    *entire* ~2-year CSV (not just one short window) so the agreement
    rate reflects multiple market regimes (bull/bear/sideways)
    instead of one arbitrary slice — cheap to do since each sample
    only recomputes indicators over a bounded sliding window.
    """

    @classmethod
    def setUpClass(cls):
        cls.strategy = CrossOverStrategyV1()
        cls.full_df = _load_ohlcv_csv(CSV_PATH)

        # "vector style": ONE batch computation over the entire
        # available history, mirroring VectorBacktestService feeding
        # generate_signal_series() data spanning
        # [start_date - warmup_window * timeframe, end_date] — here
        # start_date is simply the first row of the CSV.
        cls.vector_indicators = cls.strategy._prepare_indicators(
            cls.full_df.copy()
        )

        # Bars with at least WARMUP_BARS of true prior history,
        # sampled every FULL_HISTORY_SAMPLE_STRIDE-th bar so the
        # check spans the whole file cheaply.
        usable = cls.vector_indicators.iloc[WARMUP_BARS:]
        cls.window_bars = usable.index[
            ::FULL_HISTORY_SAMPLE_STRIDE
        ].tolist()
        assert len(cls.window_bars) > 0, (
            "No bars found in the configured window — CSV fixture or "
            "date range configuration is broken."
        )

    def _event_style_indicators(self, bar_time):
        """Recompute indicators fresh on a sliding ``WARMUP_BARS``-bar
        window ending at ``bar_time`` and return the last row's
        ``(entry, exit)`` booleans together — mirrors exactly what
        the event engine does per tick (``OHLCVDataProvider.
        get_backtest_data`` slices ``[bar_time - WARMUP_BARS bars,
        bar_time]``, and ``signals_from_column`` only ever looks at
        the *last* row of whatever it's given), and avoids
        recomputing the same sliding window twice per bar.
        """
        start = bar_time - timedelta(minutes=BAR_MINUTES * WARMUP_BARS)
        sliding_window = self.full_df.loc[
            (self.full_df.index >= start) & (self.full_df.index <= bar_time)
        ].copy()
        result = self.strategy._prepare_indicators(sliding_window)
        last = result.iloc[-1]
        return bool(last["entry"]), bool(last["exit"])

    def test_first_bar_matches_exactly(self):
        """At the very first sampled bar, the vector engine's batch
        (starting from the file's first row) and the event engine's
        sliding window cover the *exact same* underlying rows by
        construction — so they must agree exactly. A failure here
        means the two slicing strategies aren't equivalent even in
        the trivial case, which would point at a real bug rather
        than the documented sliding-window limitation.
        """
        first_bar = self.window_bars[0]
        event_entry, event_exit = self._event_style_indicators(first_bar)
        vector_entry = bool(self.vector_indicators.loc[first_bar, "entry"])
        vector_exit = bool(self.vector_indicators.loc[first_bar, "exit"])
        self.assertEqual(
            vector_entry, event_entry,
            f"entry: mismatch on the very first sampled bar "
            f"({first_bar}), where both slicing strategies should "
            f"cover identical underlying data."
        )
        self.assertEqual(
            vector_exit, event_exit,
            f"exit: mismatch on the very first sampled bar "
            f"({first_bar}), where both slicing strategies should "
            f"cover identical underlying data."
        )

    def test_bar_level_agreement_rate(self):
        """Quantify how often the two feeding strategies agree across
        the sampled bars, for both the entry and exit columns. This
        documents (rather than hides) the known sliding-window-vs-
        growing-batch divergence, while still catching a regression
        that pushes agreement far down.
        """
        mismatches = {"entry": 0, "exit": 0}
        for bar_time in self.window_bars:
            event_entry, event_exit = self._event_style_indicators(bar_time)
            vector_entry = bool(
                self.vector_indicators.loc[bar_time, "entry"]
            )
            vector_exit = bool(self.vector_indicators.loc[bar_time, "exit"])
            if vector_entry != event_entry:
                mismatches["entry"] += 1
            if vector_exit != event_exit:
                mismatches["exit"] += 1

        total = len(self.window_bars)
        for column, count in mismatches.items():
            agreement = 1 - count / total
            self.assertGreaterEqual(
                agreement, 0.85,
                f"{column}: vector/event indicator agreement "
                f"{agreement:.1%} is lower than expected "
                f"({count}/{total} sampled bars disagree)"
            )


class TestEngineLevelTradeParity(TestCase):
    """Run :class:`CrossOverStrategyV1` through both engines end to
    end, on the same fixed real BTC/EUR dataset and date range, and
    compare the resulting trades.

    Given the documented indicator-computation difference (see
    :class:`TestSignalGenerationParity`), exact trade-for-trade
    equality is not guaranteed. Empirically (verified against this
    exact dataset/strategy/window), the divergence does *not* show up
    as a uniform timing drift across all trades — it shows up as the
    event engine occasionally firing a handful of *extra* short
    trades that the vector engine doesn't, interspersed among an
    otherwise near-identical trade sequence. So trades are matched by
    nearest ``opened_at`` (not by strict chronological position),
    and the assertions separately check:

      * every vector trade has a close event counterpart (the vector
        engine's signals are effectively a subset of the event
        engine's);
      * matched pairs open within a small tolerance of each other;
      * the event engine's "extra" trades stay a minority of its
        total trade count.

    Uses a 365-day window (rather than the 30-day window used
    elsewhere in the event-backtest suite) because a short window
    gives too few trades for any of the above to be statistically
    meaningful — with only 2-5 trades, a single extra/missing signal
    swings the numbers wildly. At 365 days this strategy/dataset
    produces ~18 vector / ~22 event trades, which is enough for a
    single extra/missing trade to move the ratios by only a few
    percentage points instead of ~10%. See
    :class:`TestEngineLevelTradeParityFullHistory` for the (skipped
    by default) full ~2-year variant.
    """

    ENGINE_WINDOW_DAYS = 365
    MATCH_TOLERANCE = timedelta(days=2)
    TIGHT_MATCH_TOLERANCE = timedelta(hours=6)
    MIN_VECTOR_MATCH_RATE = 0.9
    MIN_TIGHT_MATCH_RATE = 0.80
    MAX_EVENT_EXTRA_RATE = 0.30

    vector_run = None
    event_run = None

    @classmethod
    def setUpClass(cls):
        resource_directory = str(RESOURCES_DIR)
        config = {RESOURCE_DIRECTORY: resource_directory}
        date_range = BacktestDateRange(
            start_date=END_DATE - timedelta(days=cls.ENGINE_WINDOW_DAYS),
            end_date=END_DATE,
        )

        # NOTE: explicit CSVOHLCVDataProvider registration is used
        # here rather than the DATA_DIRECTORY auto-discovery
        # convention — the latter is currently broken for this data
        # source shape on `main` (see repo memory notes), unrelated
        # to vector/event parity.
        app_vector = create_app(name="VectorSignalParity", config=config)
        app_vector.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        app_vector.add_data_provider(
            data_provider=CSVOHLCVDataProvider(
                storage_path=str(CSV_PATH),
                symbol="BTC/EUR",
                time_frame="2h",
                market="BITVAVO",
                warmup_window=WARMUP_BARS,
            ),
            priority=1,
        )
        vector_backtest = app_vector.run_vector_backtest(
            strategy=CrossOverStrategyV1(algorithm_id="vector_parity"),
            backtest_date_range=date_range,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
        )
        cls.vector_run = vector_backtest.get_all_backtest_runs()[0]

        app_event = create_app(name="EventSignalParity", config=config)
        app_event.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        app_event.add_data_provider(
            data_provider=CSVOHLCVDataProvider(
                storage_path=str(CSV_PATH),
                symbol="BTC/EUR",
                time_frame="2h",
                market="BITVAVO",
                warmup_window=WARMUP_BARS,
            ),
            priority=1,
        )
        event_backtest = app_event.run_backtest(
            strategy=CrossOverStrategyV1(algorithm_id="event_parity"),
            backtest_date_range=date_range,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
        )
        cls.event_run = event_backtest.get_all_backtest_runs()[0]

        cls.v_trades = sorted(
            cls.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        cls.e_trades = sorted(
            cls.event_run.get_trades(), key=lambda t: t.opened_at
        )
        cls.matched_pairs, cls.unmatched_v, cls.unmatched_e = (
            _match_trades_by_open_time(
                cls.v_trades, cls.e_trades, cls.MATCH_TOLERANCE
            )
        )

    def test_both_engines_traded(self):
        """Sanity check: the strategy/dataset combination actually
        produces trades in both engines, so the comparisons below are
        meaningful (not vacuously true on empty trade lists)."""
        self.assertGreater(len(self.v_trades), 0)
        self.assertGreater(len(self.e_trades), 0)

    def test_almost_every_vector_trade_has_a_close_event_counterpart(self):
        """The vector engine's (fewer, more stable) trades should
        each have a nearby event-engine trade — i.e. vector's signals
        are effectively a subset of event's, not a diverging set."""
        match_rate = len(self.matched_pairs) / len(self.v_trades)
        self.assertGreaterEqual(
            match_rate, self.MIN_VECTOR_MATCH_RATE,
            f"Only {len(self.matched_pairs)}/{len(self.v_trades)} "
            f"vector trades ({match_rate:.0%}) had an event-engine "
            f"trade opening within {self.MATCH_TOLERANCE}. Unmatched "
            f"vector trades: "
            f"{[t.opened_at for t in self.unmatched_v]}"
        )

    def test_matched_trades_open_very_close_together(self):
        """For the matched pairs, most should open within a tight
        (6h / 3-bar) tolerance — the coarser 2-day match tolerance
        above only exists to survive the rare larger nudge."""
        tight_matches = sum(
            1 for vt, et in self.matched_pairs
            if abs(vt.opened_at - et.opened_at) <= self.TIGHT_MATCH_TOLERANCE
        )
        tight_rate = tight_matches / len(self.matched_pairs)
        self.assertGreaterEqual(
            tight_rate, self.MIN_TIGHT_MATCH_RATE,
            f"Only {tight_matches}/{len(self.matched_pairs)} matched "
            f"pairs ({tight_rate:.0%}) opened within "
            f"{self.TIGHT_MATCH_TOLERANCE} of each other."
        )

    def test_event_extra_trades_stay_a_minority(self):
        """The event engine's occasional extra trades (see class
        docstring) should stay a minority of its total trades — a
        regression that causes it to fire wildly more (or the vector
        engine wildly fewer) should fail this."""
        extra_rate = len(self.unmatched_e) / len(self.e_trades)
        self.assertLessEqual(
            extra_rate, self.MAX_EVENT_EXTRA_RATE,
            f"{len(self.unmatched_e)}/{len(self.e_trades)} "
            f"({extra_rate:.0%}) event trades have no close vector "
            f"counterpart — expected these 'extra' trades to stay a "
            f"minority. Extras: "
            f"{[t.opened_at for t in self.unmatched_e]}"
        )

    def test_matched_trades_have_same_symbol(self):
        """Matched trades should agree on symbol (both engines only
        trade BTC here, so this also guards against a stray/extra
        symbol creeping into either side)."""
        for vt, et in self.matched_pairs:
            v_sym = getattr(vt, "symbol", None) or \
                getattr(vt, "target_symbol", None)
            e_sym = getattr(et, "symbol", None) or \
                getattr(et, "target_symbol", None)
            self.assertEqual(
                v_sym, e_sym,
                f"Matched trade pair symbol mismatch: "
                f"vector={vt.opened_at}/{v_sym}, "
                f"event={et.opened_at}/{e_sym}"
            )


class TestEngineParityWithRecommendedWarmup(TestCase):
    """The concrete, actionable fix for the divergence documented on
    :class:`TestSignalGenerationParity`/:class:`TestEngineLevelTradeParity`:
    give both engines a ``warmup_window`` of **2x** the strategy's
    slowest indicator period (here EMA-200, so 400 bars) instead of
    1x. More warmup bars means the event engine's per-tick sliding
    window and the vector engine's growing batch have both converged
    the EMA-200 to (numerically) the same steady state, so the
    "fresh reseed vs long-accumulated batch" gap that causes the
    divergence shrinks to noise.

    Empirically verified (this exact dataset/strategy/365-day window):
    at ``warmup_window=200`` (1x) vector/event produced 18/22 trades
    (4 unmatched "extra" event trades, 88.9% tight-match rate); at
    ``warmup_window=400`` (2x) they produced an **identical 19/19**
    trades, matched 1:1, **100%** within 6 hours of each other. This
    is the evidence backing the "use a longer warmup_window" guidance
    in the vector/event engine parity docs.
    """

    ENGINE_WINDOW_DAYS = 365
    RECOMMENDED_WARMUP_BARS = WARMUP_BARS * 2  # 2x the slowest indicator period
    MATCH_TOLERANCE = timedelta(days=2)
    TIGHT_MATCH_TOLERANCE = timedelta(hours=6)
    MAX_TRADE_COUNT_DIFF = 1
    MIN_TIGHT_MATCH_RATE = 0.95

    @classmethod
    def setUpClass(cls):
        resource_directory = str(RESOURCES_DIR)
        config = {RESOURCE_DIRECTORY: resource_directory}
        date_range = BacktestDateRange(
            start_date=END_DATE - timedelta(days=cls.ENGINE_WINDOW_DAYS),
            end_date=END_DATE,
        )

        def _make_data_provider():
            return CSVOHLCVDataProvider(
                storage_path=str(CSV_PATH),
                symbol="BTC/EUR",
                time_frame="2h",
                market="BITVAVO",
                warmup_window=cls.RECOMMENDED_WARMUP_BARS,
            )

        def _make_strategy(algorithm_id):
            # CrossOverStrategyV1 hardcodes warmup_window=self.trend
            # (200, i.e. 1x) on its own DataSource — bump it to match
            # the provider's larger warmup so both engines see the
            # same, longer history.
            strategy = CrossOverStrategyV1(algorithm_id=algorithm_id)
            strategy.data_sources[0] = dataclasses.replace(
                strategy.data_sources[0],
                warmup_window=cls.RECOMMENDED_WARMUP_BARS,
            )
            return strategy

        app_vector = create_app(
            name="VectorRecommendedWarmup", config=config
        )
        app_vector.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        app_vector.add_data_provider(
            data_provider=_make_data_provider(), priority=1
        )
        vector_backtest = app_vector.run_vector_backtest(
            strategy=_make_strategy("vector_warmup2x"),
            backtest_date_range=date_range,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
        )
        cls.vector_run = vector_backtest.get_all_backtest_runs()[0]

        app_event = create_app(name="EventRecommendedWarmup", config=config)
        app_event.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        app_event.add_data_provider(
            data_provider=_make_data_provider(), priority=1
        )
        event_backtest = app_event.run_backtest(
            strategy=_make_strategy("event_warmup2x"),
            backtest_date_range=date_range,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
        )
        cls.event_run = event_backtest.get_all_backtest_runs()[0]

        cls.v_trades = sorted(
            cls.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        cls.e_trades = sorted(
            cls.event_run.get_trades(), key=lambda t: t.opened_at
        )
        cls.matched_pairs, cls.unmatched_v, cls.unmatched_e = (
            _match_trades_by_open_time(
                cls.v_trades, cls.e_trades, cls.MATCH_TOLERANCE
            )
        )

    def test_both_engines_traded(self):
        self.assertGreater(len(self.v_trades), 0)
        self.assertGreater(len(self.e_trades), 0)

    def test_trade_counts_are_almost_identical(self):
        """With 2x warmup, both engines should produce essentially
        the same number of trades — unlike the 1x-warmup case, where
        event produced ~20% more trades than vector."""
        diff = abs(len(self.v_trades) - len(self.e_trades))
        self.assertLessEqual(
            diff, self.MAX_TRADE_COUNT_DIFF,
            f"Trade count difference {diff} exceeds "
            f"{self.MAX_TRADE_COUNT_DIFF}: "
            f"vector={len(self.v_trades)}, event={len(self.e_trades)}"
        )

    def test_almost_no_unmatched_trades(self):
        """With 2x warmup, essentially every trade on either side
        should have a close counterpart on the other — unlike the
        1x-warmup case, where the event engine had several
        unmatched "extra" trades."""
        self.assertLessEqual(len(self.unmatched_v), self.MAX_TRADE_COUNT_DIFF)
        self.assertLessEqual(len(self.unmatched_e), self.MAX_TRADE_COUNT_DIFF)

    def test_matched_trades_open_very_close_together(self):
        """With 2x warmup, matched pairs should overwhelmingly open
        within a tight (6h) tolerance of each other."""
        tight_matches = sum(
            1 for vt, et in self.matched_pairs
            if abs(vt.opened_at - et.opened_at) <= self.TIGHT_MATCH_TOLERANCE
        )
        tight_rate = tight_matches / len(self.matched_pairs)
        self.assertGreaterEqual(
            tight_rate, self.MIN_TIGHT_MATCH_RATE,
            f"Only {tight_matches}/{len(self.matched_pairs)} matched "
            f"pairs ({tight_rate:.0%}) opened within "
            f"{self.TIGHT_MATCH_TOLERANCE} of each other."
        )


@unittest.skip(
    "Slow (~90s: full ~2-year event-mode backtest) — opt-in for "
    "periodic/manual deeper verification, not run by default CI. "
    "Remove this skip to run locally when validating changes to the "
    "vector/event engines or CrossOverStrategyV1."
)
class TestEngineLevelTradeParityFullHistory(TestEngineLevelTradeParity):
    """Same checks as :class:`TestEngineLevelTradeParity`, over the
    *entire* ~2-year CSV history (730 days) for maximum statistical
    confidence — ~38 vector / ~42 event trades (verified: 97% vector
    match rate, 87% tight-match rate, 12% event extra-rate — all
    comfortably inside the inherited tolerances) — at the cost of a
    much slower event-mode backtest (~90s total).
    """

    ENGINE_WINDOW_DAYS = 730

