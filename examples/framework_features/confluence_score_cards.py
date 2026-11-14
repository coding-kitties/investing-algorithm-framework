"""Use a ConfluenceCard as the entry decision inside a strategy.

Run with:

    python3 examples/framework_features/confluence_score_cards.py
"""
import json
from dataclasses import replace
from itertools import product
from typing import Any, Iterator, Mapping

import pandas as pd

from investing_algorithm_framework import (
    AllOf,
    AnyOf,
    AtLeast,
    Condition,
    ConditionExpression,
    ConfluenceCard,
    DECISION_TRACE_METADATA_KEY,
    EvaluationContext,
    EvidenceGroup,
    Expression,
    Not,
    Operator,
    PrimaryGroup,
    Schedule,
    ScoreRule,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    condition,
)


def _conditions(expression: Expression) -> Iterator[Condition]:
    if isinstance(expression, ConditionExpression):
        yield expression.condition
    elif isinstance(expression, (AllOf, AnyOf, AtLeast)):
        for child in expression.expressions:
            yield from _conditions(child)
    elif isinstance(expression, Not):
        yield from _conditions(expression.expression)
    else:
        raise TypeError("Use built-in confluence expressions")


def custom_condition(
    dataframe: pd.DataFrame,
    expected_values: Mapping[str, Any] | Expression | Condition,
) -> bool:
    """
    Evaluate a mapping or expression against the final DataFrame row.

    Crossings use the penultimate row. Supply rows in chronological order.
    Any required null or unavailable history rejects the whole expression,
    including OR and NOT expressions. Missing columns raise KeyError.
    """
    if isinstance(expected_values, Mapping):
        if not expected_values:
            raise ValueError("Provide at least one expected column value")
        if pd.Series(expected_values).isna().any():
            return False
        expression = AllOf(tuple(
            condition(column, Operator.EQ, value=value)
            for column, value in expected_values.items()
        ))
    elif isinstance(expected_values, Condition):
        expression = ConditionExpression(expected_values)
    else:
        expression = expected_values

    current_columns = set()
    previous_columns = set()
    for predicate in _conditions(expression):
        columns = {
            f"{predicate.timeframe}:{name}" if predicate.timeframe else name
            for name in (predicate.indicator, predicate.reference)
            if name is not None
        }
        current_columns.update(columns)
        if predicate.operator in (Operator.CROSS_ABOVE, Operator.CROSS_BELOW):
            previous_columns.update(columns)
        if predicate.reference is None:
            constants = (
                predicate.value if predicate.operator is Operator.BETWEEN
                else [predicate.value]
            )
            if pd.Series(constants).isna().any():
                return False

    if not dataframe.columns.is_unique:
        raise ValueError("DataFrame column names must be unique")
    selected = dataframe.loc[:, sorted(current_columns)]
    if selected.empty or (previous_columns and len(selected) < 2):
        return False
    last_row = selected.iloc[-1]
    previous_row = (
        selected.iloc[-2].loc[sorted(previous_columns)]
        if previous_columns else pd.Series(dtype=object)
    )
    if last_row.isna().any() or previous_row.isna().any():
        return False
    return bool(expression.evaluate(EvaluationContext(
        values=last_row.to_dict(), previous_values=previous_row.to_dict(),
    )))


confirmed_setup = condition("confirmed_setup", Operator.EQ, value=True)
confirmed_short_setup = condition(
    "confirmed_short_setup", Operator.EQ, value=True
)
rsi_reversal = condition("rsi", Operator.CROSS_ABOVE, value=30)
macd_reversal = condition("macd", Operator.CROSS_ABOVE, value=0)
rsi_bearish_reversal = condition("rsi", Operator.CROSS_BELOW, value=70)
macd_bearish_reversal = condition("macd", Operator.CROSS_BELOW, value=0)
stoch_oversold = condition("stoch", Operator.LT, value=20)
above_ema_50 = condition("close", Operator.GT, reference="ema_50")
below_ema_50 = condition("close", Operator.LT, reference="ema_50")
volume_expansion = condition(
    "volume", Operator.GT, reference="average_volume"
)

CUSTOM_SETUP = AllOf((
    condition("trend", Operator.EQ, value="bullish"),
    condition("rsi", Operator.BETWEEN, value=(30, 70)),
    AnyOf((
        condition("volume_confirmed", Operator.EQ, value=True),
        volume_expansion,
    )),
    Not(condition("close", Operator.LT, reference="ema_50")),
))

CUSTOM_SHORT_SETUP = AllOf((
    condition("trend", Operator.EQ, value="bearish"),
    condition("rsi", Operator.BETWEEN, value=(30, 70)),
    AnyOf((
        condition("volume_confirmed", Operator.EQ, value=True),
        volume_expansion,
    )),
    Not(condition("close", Operator.GT, reference="ema_50")),
))


ENTRY_CONFLUENCE_CARD = ConfluenceCard(
    name="Long reversal",
    primary=PrimaryGroup(
        name="reversal",
        rules=(
            ScoreRule(
                name="RSI crosses above 30", expression=rsi_reversal, points=3,
            ),
            ScoreRule(
                name="MACD crosses above 0",
                expression=macd_reversal, points=3,
            ),
            ScoreRule(
                name="Stochastic below 20",
                expression=stoch_oversold, points=2,
            ),
        ),
        minimum_matches=2,
        minimum_score=5,
    ),
    secondary=(
        EvidenceGroup(
            name="confirmation",
            rules=(
                ScoreRule(
                    name="Close above EMA50",
                    expression=above_ema_50, points=2,
                ),
                ScoreRule(
                    name="Volume above average",
                    expression=volume_expansion, points=1,
                ),
                ScoreRule(
                    name="Last row confirms bullish setup",
                    expression=confirmed_setup, points=1,
                ),
            ),
            minimum_score=2,
        ),
    ),
    minimum_score=7,
)

EXIT_CONFLUENCE_CARD = ConfluenceCard(
    name="Exit reversal",
    primary=PrimaryGroup(
        name="exit",
        rules=(
            ScoreRule(
                name="RSI crosses below 70",
                expression=rsi_bearish_reversal, points=3,
            ),
            ScoreRule(
                name="MACD crosses below 0",
                expression=macd_bearish_reversal, points=3,
            ),
        ),
        minimum_matches=1,
        minimum_score=3,
    ),
    minimum_score=3,
)

ENTRY_SHORT_CONFLUENCE_CARD = ConfluenceCard(
    name="Short reversal",
    primary=PrimaryGroup(
        name="reversal",
        rules=(
            ScoreRule(
                name="RSI crosses below 70",
                expression=rsi_bearish_reversal, points=3,
            ),
            ScoreRule(
                name="MACD crosses below 0",
                expression=macd_bearish_reversal, points=3,
            ),
        ),
        minimum_matches=2,
        minimum_score=5,
    ),
    secondary=(
        EvidenceGroup(
            name="confirmation",
            rules=(
                ScoreRule(
                    name="Close below EMA50",
                    expression=below_ema_50, points=2,
                ),
                ScoreRule(
                    name="Volume above average",
                    expression=volume_expansion, points=1,
                ),
                ScoreRule(
                    name="Last row confirms bearish setup",
                    expression=confirmed_short_setup, points=1,
                ),
            ),
            minimum_score=2,
        ),
    ),
    minimum_score=7,
)
EXIT_SHORT_CONFLUENCE_CARD = ConfluenceCard(
    name="Exit short reversal",
    primary=PrimaryGroup(
        name="exit",
        rules=(
            ScoreRule("RSI crosses above 30", rsi_reversal, 3),
            ScoreRule("MACD crosses above 0", macd_reversal, 3),
        ),
        minimum_matches=1,
        minimum_score=3,
    ),
    minimum_score=3,
)


def build_entry_card(
    *, short=False, minimum_score=7, primary_minimum_score=5,
    primary_minimum_matches=2, confirmation_minimum_score=2,
    rsi_threshold=None, rsi_points=3,
) -> ConfluenceCard:
    template = ENTRY_SHORT_CONFLUENCE_CARD if short else ENTRY_CONFLUENCE_CARD
    if rsi_threshold is None:
        rsi_threshold = 70 if short else 30
    operator = Operator.CROSS_BELOW if short else Operator.CROSS_ABOVE
    direction = "below" if short else "above"
    rsi_rule = replace(
        template.primary.rules[0],
        name=f"RSI crosses {direction} {rsi_threshold:g}",
        expression=condition("rsi", operator, value=rsi_threshold),
        points=rsi_points,
    )
    return replace(
        template, minimum_score=minimum_score,
        primary=replace(
            template.primary, rules=(rsi_rule,) + template.primary.rules[1:],
            minimum_matches=primary_minimum_matches,
            minimum_score=primary_minimum_score,
        ),
        secondary=(replace(
            template.secondary[0], minimum_score=confirmation_minimum_score,
        ),),
    )


def build_exit_card(
    *, short=False, minimum_score=3, rsi_threshold=None,
) -> ConfluenceCard:
    template = EXIT_SHORT_CONFLUENCE_CARD if short else EXIT_CONFLUENCE_CARD
    if rsi_threshold is None:
        rsi_threshold = 30 if short else 70
    operator = Operator.CROSS_ABOVE if short else Operator.CROSS_BELOW
    direction = "above" if short else "below"
    rsi_rule = replace(
        template.primary.rules[0],
        name=f"RSI crosses {direction} {rsi_threshold:g}",
        expression=condition("rsi", operator, value=rsi_threshold),
    )
    return replace(
        template, minimum_score=minimum_score,
        primary=replace(
            template.primary, rules=(rsi_rule,) + template.primary.rules[1:],
        ),
    )


class ConfluenceEntryStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)
    symbols = ["BTC"]
    signal_cards = {
        SignalSide.OPEN_LONG: ENTRY_CONFLUENCE_CARD,
        SignalSide.CLOSE_LONG: EXIT_CONFLUENCE_CARD,
        SignalSide.OPEN_SHORT: ENTRY_SHORT_CONFLUENCE_CARD,
        SignalSide.CLOSE_SHORT: EXIT_SHORT_CONFLUENCE_CARD,
    }

    def __init__(
        self, *,
        entry_minimum_score=7,
        exit_minimum_score=3,
        short_entry_minimum_score=7,
        short_exit_minimum_score=3,
        primary_minimum_score=5,
        primary_minimum_matches=2,
        confirmation_minimum_score=2,
        rsi_oversold=30,
        rsi_overbought=70,
        rsi_points=3,
        **kwargs,
    ):
        if not 0 <= rsi_oversold < rsi_overbought <= 100:
            raise ValueError(
                "RSI thresholds must satisfy 0 <= low < high <= 100"
            )
        entry_settings = {
            "primary_minimum_score": primary_minimum_score,
            "primary_minimum_matches": primary_minimum_matches,
            "confirmation_minimum_score": confirmation_minimum_score,
            "rsi_points": rsi_points,
        }
        cards = {
            SignalSide.OPEN_LONG: build_entry_card(
                minimum_score=entry_minimum_score,
                rsi_threshold=rsi_oversold, **entry_settings,
            ),
            SignalSide.CLOSE_LONG: build_exit_card(
                minimum_score=exit_minimum_score, rsi_threshold=rsi_overbought,
            ),
            SignalSide.OPEN_SHORT: build_entry_card(
                short=True, minimum_score=short_entry_minimum_score,
                rsi_threshold=rsi_overbought, **entry_settings,
            ),
            SignalSide.CLOSE_SHORT: build_exit_card(
                short=True, minimum_score=short_exit_minimum_score,
                rsi_threshold=rsi_oversold,
            ),
        }
        metadata = dict(kwargs.pop("metadata", None) or {})
        metadata["confluence_parameters"] = {
            "entry_minimum_score": entry_minimum_score,
            "exit_minimum_score": exit_minimum_score,
            "short_entry_minimum_score": short_entry_minimum_score,
            "short_exit_minimum_score": short_exit_minimum_score,
            **entry_settings,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
        }
        metadata["confluence_cards"] = {
            side.value: card.to_dict() for side, card in cards.items()
        }
        super().__init__(signal_cards=cards, metadata=metadata, **kwargs)
        self.custom_setup = AllOf((
            CUSTOM_SETUP.expressions[0],
            condition("rsi", Operator.BETWEEN,
                      value=(rsi_oversold, rsi_overbought)),
            *CUSTOM_SETUP.expressions[2:],
        ))
        self.custom_short_setup = AllOf((
            CUSTOM_SHORT_SETUP.expressions[0],
            condition("rsi", Operator.BETWEEN,
                      value=(rsi_oversold, rsi_overbought)),
            *CUSTOM_SHORT_SETUP.expressions[2:],
        ))

    def _generate_indicators(self, data):
        data = data.copy()
        indicator_columns = {
            "rsi", "macd", "stoch", "ema_50", "average_volume",
        }
        if not indicator_columns.issubset(data.columns):
            from pyindicators import rsi, macd, stochastic_oscillator, ema, sma

            data = rsi(data, source_column="close", period=14,
                       result_column="rsi")
            data = macd(data, source_column="close")
            data = stochastic_oscillator(
                data, high_column="high", low_column="low",
                close_column="close", result_column="stoch",
            )
            data["stoch"] = data["stoch_%K"]
            data = ema(data, source_column="close", period=50,
                       result_column="ema_50")
            data = sma(data, source_column="volume", period=20,
                       result_column="average_volume")
        if "trend" not in data.columns:
            data["trend"] = "neutral"
            data.loc[data["close"] > data["ema_50"], "trend"] = "bullish"
            data.loc[data["close"] < data["ema_50"], "trend"] = "bearish"
        if "volume_confirmed" not in data.columns:
            data["volume_confirmed"] = data["volume"] > data["average_volume"]
        return data

    def prepare_signal_data(self, data):
        frame = data["indicators"] if isinstance(data, Mapping) else data
        if len(frame) < 2:
            return {}
        frame = self._generate_indicators(frame)
        frame["confirmed_setup"] = self.custom_setup.evaluate_series(frame)
        frame["confirmed_short_setup"] = (
            self.custom_short_setup.evaluate_series(frame)
        )
        return {"BTC": frame}


def main() -> None:
    strategy = ConfluenceEntryStrategy()
    print(strategy.short_entry_card)
    print(strategy.short_exit_card)
    print(strategy.long_entry_card)
    print(strategy.long_exit_card)
    # data = {"indicators": pd.DataFrame([
    #     {
    #         "rsi": 29,
    #         "macd": -0.1,
    #         "trend": "neutral",
    #         "volume_confirmed": False,
    #     },
    #     {
    #         "rsi": 31,
    #         "macd": 0.2,
    #         "stoch": 24,
    #         "close": 42000,
    #         "ema_50": 41000,
    #         "volume": 900,
    #         "average_volume": 1000,
    #         "trend": "bullish",
    #         "volume_confirmed": True,
    #     },
    # ], index=pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC"))}

    # # The framework normally invokes this hook through run_strategy().
    # for signal in strategy.generate_signals(None, data):
    #     print(json.dumps(
    #         signal.metadata[DECISION_TRACE_METADATA_KEY], indent=2
    #     ))

    # for signals in strategy.generate_signal_series(data):
    #     print(json.dumps({
    #         "side": signals.side.value,
    #         "qualified_bars": int(signals.series.sum()),
    #     }))

    # for total, primary in product((7, 10), (3, 5)):
    #     variant = ConfluenceEntryStrategy(
    #         strategy_id=f"reversal_total_{total}_primary_{primary}",
    #         entry_minimum_score=total, primary_minimum_score=primary,
    #     )
    #     signals = list(variant.generate_signals(None, data))
    #     print(json.dumps({
    #         "strategy_id": variant.strategy_id,
    #         "parameters": variant.metadata["confluence_parameters"],
    #         "signals": [signal.side.value for signal in signals],
    #     }))


if __name__ == "__main__":
    main()
