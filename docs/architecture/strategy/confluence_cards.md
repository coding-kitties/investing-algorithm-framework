# Confluence cards

`ConfluenceCard` is a declarative decision model for one coherent entry or
exit hypothesis. It separates primary qualification, hard requirements,
positive or negative evidence, vetoes, and a score threshold. Evaluation is
pure: the card does not emit signals, size positions, place orders, or persist
traces.

## Strategy usage

Define the card on the strategy and evaluate it from `generate_signals` after
computing indicator values:

```python
from investing_algorithm_framework import (
    AtLeast, ConfluenceCard, condition,
    EvaluationContext, Operator, PrimaryGroup, Requirement,
    DecisionTrace, ScoreRule, Signal, SignalSide,
    TradingStrategy,
)


rsi_reversal = condition(
    indicator="rsi", operator=Operator.CROSS_ABOVE, value=30,
)
macd_reversal = condition(
    indicator="macd", operator=Operator.CROSS_ABOVE, value=0,
)
stoch_oversold = condition(
    indicator="stoch", operator=Operator.LT, value=20,
)


class ReversalStrategy(TradingStrategy):
    entry_card = ConfluenceCard(
        name="Long reversal",
        primary=PrimaryGroup(AtLeast(
            2, (rsi_reversal, macd_reversal, stoch_oversold),
        )),
        requirements=(Requirement(
            "4h trend bullish",
            condition(
                indicator="ema_50", operator=Operator.GT,
                reference="ema_200", timeframe="4h",
            ),
        ),),
        scoring=(
            ScoreRule("RSI reversal", rsi_reversal, 3, group="momentum"),
            ScoreRule("MACD reversal", macd_reversal, 3, group="momentum"),
            ScoreRule("Stoch oversold", stoch_oversold, 2,
                      group="momentum"),
        ),
        minimum_score=7,
    )

    def generate_signals(self, context, data):
        values, previous_values = self.indicator_values(data)
        evaluation_context = EvaluationContext(values, previous_values)
        result = self.entry_card.evaluate(evaluation_context)
        decision_trace = DecisionTrace.from_confluence_result(
            result, indicator_snapshot=evaluation_context,
        )

        if result.qualified:
            yield Signal(
                symbol="BTC", side=SignalSide.OPEN_LONG,
                source=self.entry_card.name,
            ).with_decision_trace(decision_trace)
        else:
            self.record_decision_trace(decision_trace, symbol="BTC")
```

The public `condition()` helper returns a `ConditionExpression` and uses the
same validation as `Condition`. It accepts `value` or `reference`, plus optional
`timeframe` and `name` arguments. Operators can be `Operator` members or their
string values (for example, `"cross_above"`). The explicit
`ConditionExpression(Condition(...))` form remains supported.

With expression-based primaries, qualification and scoring are independent.
Reusing the
same immutable expression in both places says that it participates in the
minimum primary count and contributes points. A card can therefore pass its
primary requirement but still fail its score threshold.

## Decision trace compatibility

Use `DecisionTrace`, `DecisionTraceEntry`, `Signal.with_decision_trace()`, and
`TradingStrategy.record_decision_trace()` for new code. The canonical module is
`investing_algorithm_framework.domain.models.decision_trace`; public imports
from `investing_algorithm_framework` are also supported.

Recorded non-signal decisions are available in `strategy.last_decision_traces`
and `RunReport.decision_traces`, including the `/api/run-reports` response.
Per-tick report entries use `decision_traces`, with each record carrying
`symbol` and `decision_trace`. Signal-attached traces live in
`signal.metadata["decision_trace"]` and flow through to executed orders.
The top-level report list contains explicitly recorded decisions, not a second
copy of every signal-attached trace.

Compatibility is additive, with no scheduled removal:

- `ScoreCard` and `ScoreCardEntry` alias the canonical types. The old module,
    methods, and report attributes remain supported.
- New serialized traces include `decision_trace_version` and the legacy
    `score_card_version`. Readers accept either and prefer the canonical version.
- Signal/order metadata exposes both `decision_trace` and `score_card`.
    `SCORE_CARD_METADATA_KEY` remains `"score_card"`; the canonical constant is
    `DECISION_TRACE_METADATA_KEY` (`"decision_trace"`).
- Reports expose both `decision_traces` and `score_cards`. They represent the
    same records and must not be counted twice. Canonical fields take precedence
    over legacy fields, including an explicitly empty list.
- Legacy reports and order metadata are normalized on read. Existing SQL rows
    are not rewritten merely by loading them. `SQLRunReport.decision_traces_json`
    deliberately uses the physical `score_cards_json` column so existing
    databases remain compatible with the additive migration.

These aliases preserve field-based integrations, not byte-identical JSON.
Readers that reject unknown fields must allow the new additive fields. Trace
recording still uses the current storage path; this rename does not implement
bounded streaming storage or per-bar vector trace persistence.

## Scored groups

Use `PrimaryGroup(rules=...)` when the primary rules should contribute points
as well as trigger entry. Use `EvidenceGroup` in `secondary` for confirmation
rules with their own thresholds:

```python
from investing_algorithm_framework import EvidenceGroup

entry_card = ConfluenceCard(
    name="Long reversal",
    primary=PrimaryGroup(
        name="reversal",
        rules=(
            ScoreRule("RSI reversal", rsi_reversal, 3),
            ScoreRule("MACD reversal", macd_reversal, 3),
            ScoreRule("Stoch oversold", stoch_oversold, 2),
        ),
        minimum_matches=2,
        minimum_score=5,
    ),
    secondary=(EvidenceGroup(
        name="confirmation",
        rules=(ScoreRule(
            "Above EMA50",
            ConditionExpression(Condition(
                indicator="close", operator=Operator.GT, reference="ema_50",
            )),
            2,
        ),),
        minimum_score=2,
    ),),
    minimum_score=7,
)
```

Each group evaluates its rules once. Matched points, including negative
points, contribute once to the group subtotal and the card total. Do not
repeat these rules in `scoring`, which remains an additional source of points.
`minimum_matches` counts matched rules, including negative and zero-point
rules; `minimum_score` checks their signed subtotal. Both thresholds are
inclusive and apply independently of the total threshold.

Primary rules default to one required match and no score threshold. Secondary
groups default to zero required matches and no score threshold, making them
optional supporting evidence. Setting either threshold makes that constraint
mandatory: excess points elsewhere cannot compensate for a failed group.
All secondary groups must pass their configured constraints. Requirements and
vetoes still apply.

Use either `expression` or `rules` for a primary, not both. Group names must
be unique within a card. `result.groups` and `result.to_dict()["groups"]`
expose each scored group's matches, subtotal, thresholds, and pass/fail state;
the decision trace includes these diagnostics too. Definitions round-trip
through JSON with their groups and thresholds intact. Evaluation uses the
current context only; it does not accumulate matches across a lookback window.

## Printing cards

Use `print(card)` or `str(card)` for a readable definition with the total
threshold, primary and secondary group constraints, signed rule points,
conditions, requirements, and vetoes. ASCII borders and section dividers
separate the groups; long text wraps within a maximum width of 78 columns:

```python
print(strategy.entry_card)
```

Printing does not evaluate conditions. It describes configured rules, not
their current match status. `repr(card)` remains the dataclass debugging
representation; use `card.to_dict()` for JSON serialization.

## Signal cards

`TradingStrategy.signal_cards` maps each `SignalSide` to an independent card.
The mapping can be declared on the class or passed to the base constructor;
the constructor copies it for each instance. It supports long and short entry
and exit, as well as the other signal sides. Card scores are never combined
across sides.

Configure the mapping and implement one preparation hook to inherit both
`generate_signals` and `generate_signal_series`:

```python
def prepare_signal_data(self, data):
    frame = self._generate_indicators(data["indicators"])
    frame["confirmed_setup"] = self.custom_setup.evaluate_series(frame)
    frame["confirmed_short_setup"] = (
        self.custom_short_setup.evaluate_series(frame)
    )
    return {"BTC": frame}
```

Return a dictionary of symbol-keyed pandas DataFrames with unique columns.
Indices must be unique and ascending; vector mode requires a `DatetimeIndex`.
The preparation hook runs once per signal-generation call. Compute every
custom condition column using only present and past data, and avoid mutating
shared input frames. Polars input must be converted in the preparation hook.

The event default evaluates the last row with its preceding row, emitting
traced signals and recording rejected decisions. A state-only card can
evaluate the first row; crossing cards need a preceding row. Cards with
unavailable required data are skipped without a decision trace. Other cards
for the same symbol can still qualify independently.

The vector default evaluates whole columns and emits one boolean
`SignalSeries` per symbol and side. No scalar evaluator or event hook is
called per bar. It does not create or persist per-bar decision traces, nor
attach a single row's trace to all orders. Inspect
`card.evaluate_series(frame)` for the indexed `score`, `available`, and
`qualified` columns. Unavailable rows have a missing score and false
qualification.

`expression.evaluate_series(frame)` returns pandas nullable booleans. Required
nulls or missing crossing history propagate as `pd.NA`, even through `Not`
and `AnyOf`; any unavailable expression makes its whole card unavailable.
This includes optional evidence and vetoes, preventing warm-up gaps from
silently qualifying a card. Unrelated null columns do not matter. Missing
columns raise `KeyError`. Use scalar comparison constants, or `reference`
for another column; `BETWEEN` accepts two bounds.

All built-in comparisons, logical expressions, scored groups, signed rules,
requirements, and vetoes are supported. Custom Python expression subclasses
must be converted to indicator columns for these defaults. Explicit scalar
`card.evaluate(context)` keeps its existing behavior; the default event hook
checks availability before invoking it.

Event and batch decisions agree when supplied equivalent prepared indicator
values. Indicators computed on a sliding event window can differ from those
computed on a full vector window; these defaults do not remove that upstream
difference. No resampling or timeframe alignment is performed.

Existing overrides continue to work, and strategies without `signal_cards`
retain no-op defaults. Vector validation accepts either an explicit vector
override or configured cards with a preparation-hook override.

For manual scalar workflows, you can still call this from `generate_signals`:

```python
yield from self.generate_signals_from_cards(evaluation_context, symbol="BTC")
```

Every qualifying card produces a signal with its side, card name as source,
and decision trace. Rejected cards are recorded separately for the tick. Each
trace includes `signal_side`, so entry and exit decisions remain distinct.
The normal strategy phases handle position eligibility and signal conflicts;
the helper does not suppress or prioritize qualifying sides itself. The
mapping alone does not calculate indicators: supply the preparation hook or
override the signal hooks yourself.

## Parameter sweeps

The [strategy example](../../../examples/framework_features/confluence_score_cards.py)
builds immutable cards once per instance using normal constructor parameters:

```python
from itertools import product

strategies = [
    ConfluenceEntryStrategy(
        strategy_id=f"reversal_{total}_{primary}",
        entry_minimum_score=total,
        primary_minimum_score=primary,
    )
    for total, primary in product((7, 10), (3, 5))
]
```

These are ordinary strategy instances for the existing event/vector sweep
workflow. The example's `main()` demonstrates decisions on a small frame;
it does not run a historical backtest. Supply the usual data-source, portfolio,
sizing, and backtest configuration when running a study.

The example exposes four independent total thresholds:
`entry_minimum_score`, `exit_minimum_score`, `short_entry_minimum_score`, and
`short_exit_minimum_score`. Entry cards share `primary_minimum_score`,
`primary_minimum_matches`, `confirmation_minimum_score`, and `rsi_points`.
`rsi_oversold` and `rsi_overbought` control directional crossings and the custom
setup's RSI range. Exit groups retain one required match and a three-point
primary threshold; their total thresholds are additional constraints.

`build_entry_card` and `build_exit_card` use `dataclasses.replace` without
mutating the shared templates. Metadata includes `confluence_parameters` for
constructor reconstruction and `confluence_cards` with all four resolved JSON
definitions. Preserve this metadata alongside the strategy code revision in
experiment artifacts; the custom setup computation lives in strategy code.
Card-only sweeps can reuse precomputed indicator frames, which the example
copies before preparation rather than modifying shared inputs.

The example inherits both signal hooks and demonstrates them in `main()`.
Batch evaluation allocates column arrays, not one result/trace object per bar;
the example does not add historical trace persistence or streaming storage.

## Custom DataFrame comparisons

The [strategy example](../../../examples/framework_features/confluence_score_cards.py)
includes a `custom_condition(dataframe, expected_values)` helper for pandas
DataFrames. It accepts either an equality mapping such as
`{"trend": "bullish", "volume_confirmed": True}` or a built-in confluence
expression:

```python
triggered = custom_condition(dataframe, AllOf((
    condition("rsi", Operator.BETWEEN, value=(30, 70)),
    condition("close", Operator.GT, reference="ema_50"),
    AnyOf((
        condition("macd", Operator.CROSS_ABOVE, value=0),
        condition("volume_confirmed", Operator.EQ, value=True),
    )),
)))
```

`condition` and `custom_condition` above are example-local helpers, not package
exports. All comparison operators are supported: `GT`, `GTE`, `LT`, `LTE`,
`EQ`, `NEQ`, `BETWEEN`, `CROSS_ABOVE`, and `CROSS_BELOW`. Combine them with
`AllOf`, `AnyOf`, `Not`, or `AtLeast`. A bare `Condition` is also accepted.

State comparisons use the final row; crossings use the final two rows,
including the previous reference-column value. Rows must already be in
chronological order. A timeframe uses the existing prefixed column convention,
for example `4h:ema_50`; the helper does not resample data.

An empty frame, insufficient crossing history, or any required null value
returns `False` for the whole expression, even inside OR/NOT. Unrelated null
columns do not affect evaluation. Missing columns raise `KeyError`, and
duplicate column names raise `ValueError`. This helper evaluates one decision;
it does not implement a vector signal series.

## Semantics

- Comparison operators (`GT`, `LT`, `BETWEEN`, and similar) are states and
  require only current values.
- `CROSS_ABOVE` and `CROSS_BELOW` are events and require current and previous
  values.
- Requirements cannot be compensated for by points. A matched veto always
  rejects the card, regardless of score.
- Scores are ordinal decision scores, not probabilities or confidence values.
- `group` labels preserve evidence domains in the trace. Group caps and
  correlation policies are intentionally deferred.
- `to_dict()` produces a versioned definition suitable for lineage and exact
  reconstruction with `ConfluenceCard.from_dict()`.

Use separate cards for separate hypotheses (for example, reversal and
breakout) and compose their decisions in the strategy. Sequence/within-bar
logic, timeframe-alignment expressions, group caps, optimization policy,
position sizing, and execution remain outside v1.
