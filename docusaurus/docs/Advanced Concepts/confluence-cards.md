---
sidebar_label: Confluence Cards
---

# Confluence Cards and Decision Traces

`ConfluenceCard` expresses an entry or exit decision as primary rules,
supporting evidence, hard requirements, vetoes, and a total score threshold.
It keeps strategy decisions declarative and records why a signal qualified or
was rejected.

## Define a scored decision

Use `PrimaryGroup` for the core hypothesis and `EvidenceGroup` for supporting
confirmation. Each `ScoreRule` combines a condition with a point value.

```python
from investing_algorithm_framework import (
    ConfluenceCard, EvidenceGroup, Operator, PrimaryGroup,
    ScoreRule, condition,
)

entry_card = ConfluenceCard(
    name="RSI reversal with EMA confirmation",
    primary=PrimaryGroup(
        name="reversal",
        rules=(ScoreRule(
            "RSI below 30",
            condition("rsi", Operator.LT, value=30),
            points=3,
        ),),
        minimum_matches=1,
    ),
    secondary=(EvidenceGroup(
        name="confirmation",
        rules=(ScoreRule(
            "Recent EMA crossover",
            condition("recent_crossover", Operator.GT, value=0),
            points=2,
        ),),
        minimum_score=2,
    ),),
    minimum_score=5,
)
```

Group thresholds and the total threshold are independent. A card qualifies
only when its primary group, required secondary groups, requirements, vetoes,
and total score all pass.

## Attach cards to a strategy

Map one card to each supported `SignalSide`. Long and short decisions remain
independent; their scores are never combined.

```python
class ReversalStrategy(TradingStrategy):
    signal_cards = {
        SignalSide.OPEN_LONG: long_entry_card,
        SignalSide.CLOSE_LONG: long_exit_card,
        SignalSide.OPEN_SHORT: short_entry_card,
        SignalSide.CLOSE_SHORT: short_exit_card,
    }

    def prepare_signal_data(self, data):
        frame = add_indicators(data["BTC_ohlcv"])
        return {"BTC": frame}
```

The preparation hook returns symbol-keyed pandas DataFrames. Indices must be
unique and ascending, and vector mode requires a `DatetimeIndex`. Compute
indicators from present and past data only and avoid mutating shared inputs.

With `signal_cards` and `prepare_signal_data` configured, inherited strategy
hooks provide both execution paths:

- Event-driven backtests, paper trading, and live trading evaluate the latest
  row and create a `DecisionTrace` for qualifying and rejected decisions.
- Vector backtests evaluate whole columns and emit one `SignalSeries` per
  symbol and side. They do not persist a trace for every bar.

## Conditions and availability

Use `condition()` with a constant `value` or another indicator `reference`.
Operators include comparisons, ranges, and crossings. Crossing rules require a
previous row. Missing required values make a card unavailable during warmup;
missing columns raise `KeyError`.

Logical expressions such as `AllOf`, `AnyOf`, `AtLeast`, and `Not` combine
conditions. Requirements cannot be offset by extra points, while a matching
veto rejects the card.

## Inspect traces

Event-mode traces retain the indicator snapshot, matched rules, group
subtotals, thresholds, and final qualification. Signal traces flow into order
metadata. Explicitly recorded no-op decisions are available in run reports and
the `/api/run-reports` response.

Use `card.evaluate_series(frame)` during research to inspect indexed `score`,
`available`, and `qualified` columns. Use `print(card)` to render its definition
without evaluating it.

See [Strategies](../Getting%20Started/strategies.md) and
[Event-Driven Backtesting](../Getting%20Started/event-backtesting.md).