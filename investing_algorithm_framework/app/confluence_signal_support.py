"""Compatibility support for strategies declaring concrete signal cards."""
from typing import Dict, Iterable

import pandas as pd

from investing_algorithm_framework.domain import (
    ConfluenceCard, ConfluenceScoreCard, DecisionTrace, DecisionTraceEntry,
    EvaluationContext, Signal, SignalSide, SignalSeries,
)
from ..services.confluence_reporting import (
    confluence_report_details, skipped_confluence_trace,
)


class ConfluenceSignalSupport:
    """Keep the original signal_cards API available on TradingStrategy."""

    signal_cards: Dict[SignalSide, ConfluenceCard | ConfluenceScoreCard] = None

    def _configure_signal_cards(self, signal_cards):
        configured = (
            self.signal_cards if signal_cards is None else signal_cards
        )
        self.signal_cards = dict(configured or {})
        for side, card in self.signal_cards.items():
            if not isinstance(side, SignalSide):
                raise ValueError("signal_cards keys must be SignalSide values")
            if not isinstance(card, (ConfluenceCard, ConfluenceScoreCard)):
                raise ValueError(
                    "signal_cards values must be ConfluenceCard or "
                    "ConfluenceScoreCard"
                )

    def prepare_signal_data(self, data) -> Dict[str, pd.DataFrame]:
        """Return symbol-keyed frames for concrete signal_cards evaluation.

        Override to compute causal indicators and boolean columns. Vector
        evaluation requires unique, ascending DatetimeIndex values.
        """
        raise NotImplementedError(
            "Strategies using default signal_cards hooks must implement "
            "prepare_signal_data(data) returning {symbol: pandas.DataFrame}"
        )

    def _prepared_signal_frames(self, data, *, vector=False):
        frames = self.prepare_signal_data(data)
        if not isinstance(frames, dict):
            raise TypeError("prepare_signal_data must return a symbol mapping")
        for symbol, frame in frames.items():
            if not isinstance(symbol, str) or not symbol:
                raise ValueError("Prepared signal symbols must be non-empty")
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(
                    "Prepared signal data must be pandas DataFrames"
                )
            if not frame.columns.is_unique:
                raise ValueError("Prepared signal columns must be unique")
            if vector and not isinstance(frame.index, pd.DatetimeIndex):
                raise ValueError(
                    "Vector signal frames require a DatetimeIndex"
                )
            if (not frame.index.is_unique
                    or not frame.index.is_monotonic_increasing):
                raise ValueError(
                    "Signal frame indices must be unique and sorted"
                )
            yield symbol, frame

    @staticmethod
    def _inactive_exit_reasons(context, symbol, sides):
        sides = set(sides) & {SignalSide.CLOSE_LONG, SignalSide.CLOSE_SHORT}
        if not sides:
            return {}
        trades = list(context.get_open_trades(target_symbol=symbol))
        reasons = {}
        if SignalSide.CLOSE_LONG in sides:
            has_long = any(
                not getattr(trade, "is_short", False) for trade in trades
            )
            if not has_long and not context.has_position(symbol=symbol):
                reasons[SignalSide.CLOSE_LONG] = "confluence.long_exit_requires_position"
        if SignalSide.CLOSE_SHORT in sides and not any(
            getattr(trade, "is_short", False) for trade in trades
        ):
            reasons[SignalSide.CLOSE_SHORT] = "confluence.short_exit_requires_position"
        return reasons

    def _generate_card_signals(self, data, context):
        if not self.signal_cards:
            return
        for symbol, frame in self._prepared_signal_frames(data):
            recent = frame.iloc[-2:]
            if recent.empty:
                continue
            evaluation_context = EvaluationContext(
                recent.iloc[-1].to_dict(),
                recent.iloc[-2].to_dict() if len(recent) > 1 else {},
            )
            inactive = self._inactive_exit_reasons(
                context, symbol, self.signal_cards,
            )
            for side, card in self.signal_cards.items():
                if side in inactive:
                    trace = skipped_confluence_trace(
                        card.name, side, inactive[side], evaluation_context.values,
                    )
                    self._pending_confluence_scores.append({
                        "symbol": symbol, "card_id": card.name, "side": side.value,
                        "evaluation_status": "skipped",
                        "signal_reason": inactive[side],
                        "decision_trace": trace.to_dict(),
                    })
                    self.record_decision_trace(trace, symbol=symbol)
                    continue
                availability = card.evaluate_series(recent)["available"]
                if availability.iloc[-1]:
                    yield from self._signals_from_card(
                        evaluation_context, symbol, side, card
                    )

    def generate_signals_from_cards(
        self, evaluation_context: EvaluationContext, *, symbol: str
    ) -> Iterable[Signal]:
        """Yield traced signals and record rejected card decisions."""
        for side, card in self.signal_cards.items():
            yield from self._signals_from_card(
                evaluation_context, symbol, side, card
            )

    def _signals_from_card(self, evaluation_context, symbol, side, card):
        result = card.evaluate(evaluation_context)
        trace = DecisionTrace.from_confluence_result(
            result, indicator_snapshot=evaluation_context
        )
        trace.entries.append(DecisionTraceEntry(
            name="signal_side", value=side.value, group="decision"
        ))
        trace.entries.append(DecisionTraceEntry(
            name="ready", value=True, group="decision",
        ))
        self._pending_confluence_scores.append({
            **confluence_report_details(card, result.to_dict()), "symbol": symbol,
            "card_id": card.name, "side": side.value,
            "ready": True, "passed": result.qualified,
            "decision_trace": trace.to_dict(),
        })
        if result.qualified:
            yield Signal(
                symbol=symbol, side=side, source=card.name,
            ).with_decision_trace(trace)
        else:
            self.record_decision_trace(trace, symbol=symbol)

    def _generate_card_signal_series(self, data):
        if not self.signal_cards:
            return
        for symbol, frame in self._prepared_signal_frames(data, vector=True):
            for side, card in self.signal_cards.items():
                result = card.evaluate_series(frame)
                yield SignalSeries(
                    symbol=symbol, side=side, series=result["qualified"],
                    source=card.name,
                )

    @property
    def long_entry_card(self):
        return self.signal_cards[SignalSide.OPEN_LONG]

    @property
    def short_entry_card(self):
        return self.signal_cards[SignalSide.OPEN_SHORT]

    @property
    def short_exit_card(self):
        return self.signal_cards[SignalSide.CLOSE_SHORT]

    @property
    def long_exit_card(self):
        return self.signal_cards[SignalSide.CLOSE_LONG]
