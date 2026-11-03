"""Declarative confluence strategies using the shared execution pipeline."""
from typing import Any, Dict, Iterable
from functools import partial

import pandas as pd

from investing_algorithm_framework.domain import (
    ConfluenceScoreCard, INDEX_DATETIME, Signal, SignalSide,
    SignalSeries,
)
from ..services.confluence_indicator_engine import (
    ConfluenceIndicatorEngine,
)
from ..services.indicator_engine import confluence_decision_trace
from .context import Context
from .strategy import TradingStrategy


class ConfluenceScoringStrategy(TradingStrategy):
    """Generate event signals and vector masks from named indicator cards.

    Declare indicator_configs and confluence_cards with explicit sides and
    zero-based scale-in stages. Inapplicable exit cards are skipped before
    evaluation. Cooldowns, other eligibility, exposure, sizing and orders
    remain the responsibility of the ordinary strategy phases.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.signal_cards:
            raise ValueError(
                "Use confluence_cards, not signal_cards, "
                "on ConfluenceScoringStrategy"
            )
        self._indicator_engine = self.create_indicator_engine()

    def create_indicator_engine(self):
        engine = ConfluenceIndicatorEngine(
            self.indicator_configs, self.confluence_cards,
            self.data_sources, self.symbols,
        )
        for symbol, native in engine.engines.items():
            stages = [
                card.scale_in_stage for card in native.cards.values()
                if card.side is SignalSide.SCALE_IN
            ]
            if stages:
                rule = self.get_scaling_rule(symbol)
                if rule is None or rule.max_entries != len(stages) + 1:
                    raise ValueError(
                        f"{symbol} requires a ScalingRule with "
                        f"max_entries={len(stages) + 1}"
                    )
        return engine

    def get_confluence_score_cards(self, *, merge_symbols: bool = True) -> list[ConfluenceScoreCard]:
        """Build printable configuration snapshots on demand, not during execution."""
        return self._indicator_engine.get_confluence_score_cards(merge_symbols=merge_symbols)

    def _next_scale_in_stage(self, context, symbol):
        engine = self._indicator_engine
        trades = [
            trade for trade in context.get_open_trades(target_symbol=symbol)
            if not trade.is_short and trade.filled_amount > 0
        ]
        if not trades:
            engine.entry_ids.pop(symbol, None)
            engine.entry_counts.pop(symbol, None)
            engine.entry_watermarks.pop(symbol, None)
            return None
        since = engine.entry_watermarks.get(
            symbol, min(trade.opened_at for trade in trades),
        )
        observed = {trade.id: trade for trade in trades}
        observed.update({
            trade.id: trade
            for trade in context.get_trades(
                target_symbol=symbol, opened_since=since,
            )
            if not trade.is_short and trade.filled_amount > 0
        })
        engine.entry_watermarks[symbol] = max(
            trade.opened_at for trade in observed.values()
        )
        seen = engine.entry_ids.setdefault(symbol, set())
        new_ids = observed.keys() - seen
        count = engine.entry_counts.get(symbol, 0) + len(new_ids)
        seen.update(new_ids)
        # Stage metadata also preserves progression when resuming with only
        # later lots still open after earlier lots have been closed.
        for trade in observed.values():
            if trade.id not in new_ids:
                continue
            for order in trade.orders:
                metadata = order.metadata or {}
                if "scale_in_stage" in metadata:
                    count = max(count, metadata["scale_in_stage"] + 2)
        engine.entry_counts[symbol] = count
        return count - 1

    def get_inactive_confluence_cards(self, context):
        inactive = {}
        for symbol, native in self._indicator_engine.engines.items():
            reasons = self._inactive_exit_reasons(
                context, symbol, (card.side for card in native.cards.values()),
            )
            inactive[symbol] = {
                name: reasons[card.side]
                for name, card in native.cards.items() if card.side in reasons
            }
        return inactive

    def _position_opened_at(self, context, symbol, side):
        short = side is SignalSide.CLOSE_SHORT
        trades = [
            trade for trade in context.get_open_trades(target_symbol=symbol)
            if trade.is_short == short and trade.filled_amount
        ]
        if not trades:
            raise ValueError(
                f"{symbol}: position-scoped lookback requires a filled trade "
                "with an entry timestamp; asset holdings alone are insufficient"
            )
        key = symbol, short
        anchor = self._indicator_engine.position_anchors.get(key)
        history = context.get_trades(target_symbol=symbol, opened_since=anchor)
        observed = {trade.id: trade for trade in (*history, *trades)}
        filled = [
            trade for trade in observed.values()
            if trade.is_short == short and trade.filled_amount
        ]
        if any(trade.opened_at is None for trade in filled):
            raise ValueError(f"{symbol}: a filled trade has no entry timestamp")
        since = min(pd.to_datetime(trade.opened_at, utc=True) for trade in trades)
        for trade in sorted(
            filled, key=lambda trade: pd.to_datetime(trade.opened_at, utc=True),
            reverse=True,
        ):
            opened = pd.to_datetime(trade.opened_at, utc=True)
            closed = (
                pd.to_datetime(trade.closed_at, utc=True)
                if trade.closed_at is not None else None
            )
            # Only overlapping lots belong to the same continuously held leg.
            if opened < since and (closed is None or closed > since):
                since = opened
        self._indicator_engine.position_anchors[key] = since
        return since

    def get_confluence_evaluation_options(self, context):
        inactive = self.get_inactive_confluence_cards(context)
        bounds = {}
        for symbol, native in self._indicator_engine.engines.items():
            by_side = {}
            for name in native.fill_driven_cards:
                if name in inactive[symbol]:
                    continue
                side = native.cards[name].side
                if side not in by_side:
                    by_side[side] = self._position_opened_at(context, symbol, side)
                bounds.setdefault(symbol, {})[name] = by_side[side]
        return {"inactive_cards": inactive, "position_opened_at": bounds}

    @staticmethod
    def _decision_trace(name, card, payload, values):
        return confluence_decision_trace(name, card, payload, values)

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        engine = self._indicator_engine
        options = data.get("_confluence_evaluation_options")
        supplied_options = options is not None
        if options is None:
            options = self.get_confluence_evaluation_options(context)
        inactive = options["inactive_cards"]
        evaluations = data.get("indicators")
        if evaluations is None or (options["position_opened_at"] and not supplied_options):
            evaluations = engine.evaluate(
                data, context.config[INDEX_DATETIME],
                **options,
            )
        for symbol, native in engine.engines.items():
            next_stage = (
                self._next_scale_in_stage(context, symbol)
                if symbol in engine.scale_in_symbols else None
            )
            evaluation = evaluations[symbol]
            for name, card in native.cards.items():
                reason = inactive.get(symbol, {}).get(name)
                if reason is not None:
                    evaluation.cards[name] = {
                        "evaluation_status": "skipped", "signal_reason": reason,
                    }
                payload = evaluation.cards[name]
                if payload.get("evaluation_status") == "skipped":
                    continue
                if (card.side is SignalSide.SCALE_IN
                        and card.scale_in_stage != next_stage):
                    if next_stage is None:
                        reason = "confluence.scale_in_requires_position"
                    elif card.scale_in_stage < next_stage:
                        reason = "confluence.scale_in_stage_completed"
                    else:
                        reason = "confluence.scale_in_stage_inactive"
                    payload["signal_reason"] = reason
                    continue
                trace = self._decision_trace(
                    name, card, payload, evaluation.values,
                )
                if not payload["ready"] or not payload["passed"]:
                    self.record_decision_trace(trace, symbol=symbol)
                    continue
                metadata = (
                    {"scale_in_stage": card.scale_in_stage}
                    if card.side is SignalSide.SCALE_IN else {}
                )
                yield Signal(
                    symbol=symbol, side=card.side, source=name,
                    metadata=metadata,
                ).with_decision_trace(trace)

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        engine = self.create_indicator_engine().prepare(data)
        self._vector_indicator_engine = (
            engine if any(
                native.fill_driven_cards for native in engine.engines.values()
            )
            else None
        )
        for symbol, native in engine.engines.items():
            index = native.decision_index
            if any(
                card.initial_delay or any(rule.initial_delay for rule in card.rules.values())
                for card in native.cards.values()
            ):
                index = data.get("_confluence_decision_index")
                if index is None:
                    observed = native.decision_index
                    index = pd.DatetimeIndex(
                        self.strategy_profile.schedule.iter_run_times(
                            observed.min().to_pydatetime(),
                            observed.max().to_pydatetime(),
                        ) if len(observed) else [], tz="UTC",
                    )
            sides = {card.side for card in native.cards.values()}
            for name, series in native.card_signal_series(
                index, position_scoped_candidates=True,
            ).items():
                card = native.cards[name]
                metadata = (
                    {"scale_in_stage": card.scale_in_stage}
                    if card.side is SignalSide.SCALE_IN else {}
                )
                if name in native.fill_driven_cards:
                    metadata["position_scoped_lookback"] = True
                yield SignalSeries(
                    symbol=symbol, side=card.side, series=series,
                    source=name, metadata=metadata,
                )
            # The legacy vector loop otherwise treats buys as scale-ins and
            # disables shorting unless both short-side buckets are present.
            absent = {
                SignalSide.OPEN_LONG, SignalSide.CLOSE_LONG,
                SignalSide.SCALE_IN,
            } - sides
            if sides & {SignalSide.OPEN_SHORT, SignalSide.CLOSE_SHORT}:
                absent |= {
                    SignalSide.OPEN_SHORT, SignalSide.CLOSE_SHORT,
                } - sides
            for side in sorted(absent, key=lambda value: value.value):
                yield SignalSeries(
                    symbol, side, pd.Series(False, index=index),
                )

    def _position_scoped_exit_evaluators(self):
        engine = getattr(self, "_vector_indicator_engine", None)
        if engine is None:
            raise RuntimeError("Position-scoped vector candidates must be prepared first")
        evaluators = {
            symbol: {
                side: partial(native.position_scoped_exit_signal, side=side)
                for side in {
                    native.cards[name].side
                    for name in native.fill_driven_cards
                }
            }
            for symbol, native in engine.engines.items()
            if native.fill_driven_cards
        }
        self._vector_indicator_engine = None
        return evaluators
