# Confluence cards

`ConfluenceCard` is a declarative decision model for one coherent entry or
exit hypothesis. It separates primary qualification, hard requirements,
positive or negative evidence, vetoes, and a score threshold. Evaluation is
pure: the card does not emit signals, size positions, place orders, or persist
traces.

## Strategy usage

### Declarative indicator-driven strategies

Use `ConfluenceScoringStrategy` when named `IndicatorConfig` declarations
should drive signals without a custom preparation or signal-generation hook.
The [two-hour reference strategy](../../../examples/framework_features/two_hour_confluence_strategy.py)
demonstrates a callable Z-score indicator, three entry tranches, and ordinary
strategy risk rules.

Each `ConfluenceScoreConfig` declares an explicit `side`. Scale-in cards also
declare a zero-based `scale_in_stage`: `0` is the first addition after the
initial entry. IDs are descriptive only; they never determine trading actions.
Stages must be contiguous from zero, unique per symbol, and match the scaling
rule's `max_entries` (including the initial entry).

```python
ConfluenceScoreConfig(
    id="long_scale_in_one",
    side=SignalSide.SCALE_IN,
    scale_in_stage=0,
    symbols=["BTC"],
    rules={"oversold": IndicatorRule(
        indicator_id="z_score_long", output_column="zscore",
        threshold=-2.2, comparison="le",
        group_weights={"primary": 1}, lookback_period=1,
    )},
    group_thresholds={"primary": 1},
)
```

`symbols` is optional: an empty list/tuple applies the card to all configured
strategy targets. Card symbols are normalized to uppercase. Indicator
templates can use `data_source={"BTC": "btc_2h", "ETH": "eth_2h"}` or resolve
unambiguously by symbol/timeframe. Each symbol has isolated indicator history
and scoring state. A fixed source identifier is appropriate for a card scoped
to that source's symbol. Existing `PositionSize` and `ScalingRule` still use
singular `symbol="BTC"`; `symbol=None` supplies their all-symbol default.

For a 20/40/40 ladder within a 40%-of-portfolio sizing budget, configure:

```python
PositionSize(symbol="BTC", percentage_of_portfolio=40)
ScalingRule(
    symbol="BTC", max_entries=3, initial_entry_percentage=20,
    scale_in_percentage=[40, 40], cooldown_in_bars=2,
)
```

This requests 8%, 16%, and 16% of portfolio value if the sizing base is
unchanged. Cash, exposure and other applicable execution limits can reduce
actual orders. `initial_entry_percentage` affects only the initial long
entry and defaults to 100, preserving existing strategies. Scale-in percentages
continue to refer to the full `PositionSize`, not the first tranche.

`lookback_period=1` checks the latest completed native candle. Larger windows
retain their existing "any match within the window" semantics. Neither card
qualification nor generating a signal advances the entry stage: event
progression observes filled trade lots, and vector progression uses accepted
fills. Cooldown rules retain priority. After cooldown expires the current
threshold is evaluated again; previously blocked signals are not queued.
Partial lot exits do not rewind progression; becoming fully flat resets it.

### Named required and blocking rules

Use `required_rules` and `gates` on `ConfluenceScoreConfig` to gate a
card using its named `IndicatorRule` matches:

- Every `required_rules` member must match.
- No `gates` member may match: any matching gate disables the card.
- These gates apply to both normal qualification and score overrides. More
  confirmation points cannot compensate for a failed required rule or a blocker.
- Both fields default to empty tuples and accept lists or tuples of unique,
  existing rule names. A rule cannot be both required and blocking.

For example, after registering `z_score_long` and `supertrend_filter`, a
trend-aligned long card can keep Z-score mandatory without awarding points for
the direction filter:

```python
long_entry = ConfluenceScoreConfig(
    id="long_entry",
    side=SignalSide.OPEN_LONG,
    symbols=["BTC", "ETH"],
    rules={
        "z_score_oversold": IndicatorRule(
            indicator_id="z_score_long",
            output_column="zscore",
            threshold=-2.0,
            comparison="lt",
            group_weights={"primary": 1.0},
            lookback_period=1,
        ),
        "supertrend_bearish": IndicatorRule(
            indicator_id="supertrend_filter",
            output_column="supertrend_trend",
            threshold=0.0,
            comparison="eq",
            lookback_period=1,
        ),
    },
    group_thresholds={"primary": 1.0},
    required_rules=["z_score_oversold"],
    gates=["supertrend_bearish"],
)
```

The external `indicators.supertrend` function encodes persistent bullish trend
as `1` and bearish trend as `0`. Use `supertrend_trend`, not the flip-only
`supertrend_signal`. For a short-entry card, require its positive Z-score trigger
(`gt 2.0`) and block bullish direction (`eq 1.0`). Apply the bearish blocker
to long scale-in cards too; do not attach directional gates to exit cards unless
blocking exits is explicitly intended.

`gates=["volatility_breakout"]`, for example, adds a hard veto when the
card's separately declared `volatility_breakout` rule matches. Gate references
do not change rule weights: omit `group_weights` or set it to `None` for
gate-only rules. These normalize to an immutable empty mapping and add no
scoring groups or points. An explicit empty mapping is also supported. They still
participate in the existing native-history readiness checks. Required rules
that are missing or unready do not match; unready blockers prevent signal
emission through card readiness. Use `lookback_period=1` and no rule delay for a
current directional regime, rather than retaining or delaying an older match.

Gate strings reference keys in the card's `rules` mapping, not standalone
Python variables. Unweighted rules keep their native comparisons, lookbacks,
delays, readiness checks and match evidence in inspection and persisted reports.
Required rules may be unweighted too. Omitting weights alone does not make a
rule a blocker: reference its name in `gates` to block on a match. Existing
zero-weight mappings such as `{"direction": 0.0}` remain supported.
With only a Z-score scoring rule,
`group_aggregation={"primary": "sum"}` and
`group_thresholds={"primary": 1.0}` suffice; no ADX, volume, or other entry
filters are implicit.

`blocking_rules` remains supported for compatibility. If both fields are
supplied, their names are combined in declaration order (`gates` first), with
overlapping names evaluated as a single veto. Each individual field must
still contain unique names.

Named gates supplement, rather than replace, explicit `requirements` and
`vetoes`. They compile into ordinary requirements named `required_rule:<name>`
and vetoes named `blocking_rule:<name>`, so inspection, decision evidence,
serialization and event/precomputed vector evaluation use the same scoring
contract. Those generated names must not collide with explicitly declared
gates in the corresponding category.

### Independent qualification-path readiness

`ConfluenceScoreConfig.readiness_policy` defaults to `"all_rules"`: every
declared indicator rule must be ready before the card can emit a signal,
including rules used only by overrides. This preserves existing behavior.

Opt into `"qualification_paths"` when an independent exit path should not
wait for unrelated indicator history. For example:

```python
from investing_algorithm_framework import Rule

long_exit = ConfluenceScoreConfig(
    id="long_exit",
    side=SignalSide.CLOSE_LONG,
    rules={
        "z_score": IndicatorRule(
            indicator_id="z_score_long",
            output_column="zscore",
            threshold=0.0,
            comparison="ge",
            group_weights={"primary": 1.0},
            lookback_period=14,
            lookback_scope="position",
        ),
        "supertrend_bearish": IndicatorRule(
            indicator_id="supertrend_filter",
            output_column="supertrend_trend",
            threshold=0.0,
            comparison="eq",
            lookback_period=1,
        ),
    },
    group_thresholds={"primary": 1.0},
    override_triggers=Rule("supertrend_bearish"),
    readiness_policy="qualification_paths",
)
```

The Z-score scoring path may close the position normally. Independently, a
ready bearish Supertrend rule may close it even while Z-score is warming up or
currently missing. Conversely, a ready normal exit need not wait for missing
Supertrend data. This tests the persistent bearish state, not just the flip
event. A position-scoped card still requires an actual entry-fill timestamp.
Execution remains scheduled and uses completed native candles; this does not
introduce intrabar execution or bypass rule/card delays.

Path readiness evaluates qualification using three states: known true, known
false, or unknown. Unknown data is never interpreted as a known non-match:
`Not(Rule("missing_rule"))` cannot become a ready override. `AnyOf` and `AtLeast`
can establish a path from enough known matches without waiting for unrelated
branches; `AllOf` requires all necessary matches. Conditions comparing two rule
matches require both operands to be ready.

Scoring thresholds, including `Threshold(...)` override references, require all
rules contributing to their group to be ready, preserving sum/max and signed
weight semantics. Optional groups do not hold up an otherwise established
qualification path. Hard requirements and vetoes still apply: an unknown gate
cannot permit a signal, and a known blocker always prevents it.

The card payload's `ready` flag now means the qualification decision is known,
not that every rule is ready. `passed`/`qualified` retain the existing boolean
scoring evidence; emission and decision traces require both `ready` and
`passed`. Per-rule readiness remains available separately. No historical data,
lookback, or match evidence is fabricated to make a path ready.

This policy belongs to indicator-driven evaluation, including event,
precomputed and fill-driven vector execution. A compiled `ConfluenceScoreCard`
still evaluates supplied match booleans; its standalone `evaluate_series`
does not infer native indicator readiness. Inspection snapshots retain and
display the configured readiness policy.

### Inspecting symbol-bound scoring cards

```python
for card in strategy.get_confluence_score_cards():
    print(card)
```

`ConfluenceScoringStrategy.get_confluence_score_cards()` returns one
`ConfluenceScoreCard` inspection snapshot per signal side and scale-in stage,
merging identical definitions across configured symbols by default. Card IDs,
rules, thresholds, delays, scoring policy, indicator settings and non-symbol
source settings must match; only target-symbol labels and concrete source
identifiers are ignored when comparing definitions. Different timeframes or
indicator parameters remain separate. No market data or evaluation is required.
Opaque parameter objects are compared by identity; independently copied values
whose equivalence cannot be established safely remain separate.

Merged cards print `Symbols: ETH, BTC` in strategy-symbol order and retain
separately labelled source details for every symbol. Single-symbol cards still
print `Symbol: BTC`. Symbol-scoped cards appear only for applicable targets.
Use `strategy.get_confluence_score_cards(merge_symbols=False)` to return one
card per symbol, side and stage without merging.

The boxed representation includes the card ID, symbol, side, stage, delay
mode, actual indicator comparisons and bounds, native lookbacks and scope,
weights, group aggregation/thresholds/capacities, requirements, vetoes and
overrides. Each scoring group has its own section with its aggregation,
threshold and capacity, followed by its member rules in declaration order.
Rules belonging to multiple groups appear in every applicable section with
that group's weight, including negative weights and synthetic total groups.
Indicator parameters and the resolved source's identifier, trading
pair, market and timeframe are included, so different ladder thresholds or
symbol bindings remain visible.

Inspection cards expose `symbols`, `side` and `scale_in_stage`. Merged cards
have `symbol=None` and a `symbol_cards` tuple of the individual, independent
inspection snapshots; their configuration and source metadata lives on those
snapshots rather than misleadingly selecting one symbol's binding.
Single-symbol cards additionally expose `symbol`, `configuration`
(the original `ConfluenceScoreConfig` snapshot), `indicator_configs` and
`data_sources`. The indicator registry contains only referenced calculations,
with source selectors resolved to concrete identifiers. Metadata mappings are
read-only; their contents are independent copies of the engine declarations.
Each call creates fresh snapshots, not a cached or live view. Merging changes
representation only, never per-symbol indicator history or execution state.

This API is strictly on demand: strategy construction and event/vector
evaluation do not create or format inspection snapshots. The engine continues
using its existing compiled scoring cards and native indicator state, with no
predicate evaluation or state mutation during inspection. The scoring behavior
of returned cards is unchanged; their `evaluate` methods still consume
compiled rule-match booleans, not raw indicator values. Inspection does not
make them an alternative execution engine.

Ordinary `ConfluenceScoreCard` objects retain their existing text format.
Scoring equality and `to_dict()`/`from_dict()` remain unchanged and exclude
inspection metadata; pickle preserves the inspection snapshot. Use the
exposed configuration and indicator registrations when exporting declarations.

### Delayed confirmation and bounded indicator rules

Set `initial_delay=N` on each `IndicatorRule` to wait N **scheduled strategy
evaluations** after that rule first matches and is ready. For example, a trigger at
t with `initial_delay=3` can first emit at t+3, not t+2. The default is 0,
preserving immediate signals.

`initial_delay_mode="continuous"` (default) requires the rule to match on every
evaluation; losing the match or readiness resets the countdown.
`initial_delay_mode="recheck"` ignores intermediate match changes and
checks again at t+N. A failed deadline resets the countdown, and a later trigger
starts a new one. After confirmation, a still-matching rule contributes its weight
on subsequent evaluations; losing the match rearms the delay. Delays filter rule
matches after their lookback and before weights, group scoring, requirements,
vetoes and overrides. Undelayed rules contribute immediately; a pending rule does
not block the whole group.
Repeated evaluation at the same timestamp never advances the countdown.

State is isolated per rule, card and symbol and reset for each backtest run. Skipped
cards reset their delays; a new filled position starts fresh. Entry and
scale-in countdowns track rule matches independently of position
eligibility and cooldowns: confirmation does not queue orders or consume stages.
Event evidence records each delayed rule under `rule_delays`, including
`raw_matched`, `matched`, `initial_delay`, `initial_delay_mode`, `delay_elapsed`
and `delay_pending`. Rule evaluations and decision traces include this evidence.
`ConfluenceScoreConfig` also supports `initial_delay` and `initial_delay_mode`:
they delay whole-card qualification after rule-level scoring. Both levels may be
enabled together, with independent delay lengths and modes. For a continuously
matching rule, a rule delay of 1 followed by a card delay of 2 confirms at t+3.
Card evidence uses `raw_passed` for qualification before the card delay;
`passed`/`qualified` reflect the final delayed result.

For an inclusive interval, add `lower_bound` and/or `upper_bound` to an
`IndicatorRule`. These are ANDed with its existing comparison **on the same
native observation**, before the rolling-any lookback, and contribute the
rule's weight only once:

```python
ConfluenceScoreConfig(
    id="bounded_entry", side=SignalSide.OPEN_LONG,
    rules={"oversold": IndicatorRule(
        indicator_id="zscore", output_column="zscore",
        threshold=-2, comparison="le", lower_bound=-3,
        group_weights={"primary": 1},
        initial_delay=3, initial_delay_mode="continuous",
    )},
    group_thresholds={"primary": 1},
)
```

This accepts exactly `-3 <= zscore <= -2`. Bounds must be finite and ordered;
missing indicator values never match. Recorded conditions include both bounds.

Both event and vector backtests support delay modes and bounds. With delayed
rules or cards, vector masks use the actual backtest schedule, not candle counts or
warm-up rows, including evaluations between candle completions. Delayed exits
use fill-driven vector evaluation, like position-scoped exits, and share its
Python-backend requirement. For direct `generate_signal_series(data)` calls
outside a backtest, the schedule spans the supplied native history; supply
`data["_confluence_decision_index"]` to specify the intended evaluation window.
The existing engines' order-fill timing differences remain unchanged.
Existing schedule validation still requires at least one OHLCV source as
granular as the strategy schedule. Delayed exits, like position-scoped rules,
require a recorded entry fill rather than asset holdings alone.

For `CLOSE_LONG` and `CLOSE_SHORT`, opt into a position-bounded rule window:

```python
IndicatorRule(
    indicator_id="zscore", output_column="zscore",
    threshold=0, comparison="ge", group_weights={"primary": 1},
    lookback_period=14, lookback_scope="position",
)
```

The default `lookback_scope="market"` preserves the original rolling-any
behavior. `"position"` intersects that same latest-14-native-observation window
with observations completed **strictly after the leg's first actual entry fill**.
The entry-time observation and all earlier matches are excluded. Pending or
rejected entry signals do not start a window. Scale-ins and partial closes keep
the initial boundary; fully closing and reopening starts a new one. Long and
short legs use independent boundaries in hedge mode. Continuous indicator
history and warm-up are unchanged: this does not wait for 14 post-entry candles
or restart a 14-period indicator calculation.

Event evaluation resolves the continuously held leg from filled trade history,
including overlapping lots that have since closed. An OPEN filled trade remains
part of that leg while a pending exit reserves its entire available quantity:
zero `available_amount` does not erase the entry boundary or reset scale-in
progression. Only a fully closed position resets progression. Existing asset holdings
without a recorded entry trade cannot establish this boundary and raise an
explicit error. Saved card evidence includes `position_opened_at`, and scored
indicator rules record `lookback_scope` and the boundary in their condition.
Nested trade stop-loss watermark dates are exported as ISO-8601 timestamps,
including when trailing stops update during a captured event backtest.

The subclass reuses `IndicatorEngine`, including run-local caches, shared
built-in calculations, continuous native history, and candle-completion
alignment. Event backtests prepare a fresh engine per run. Vector generation
uses ready-and-qualified masks from prepared card caches, with stage metadata,
without constructing per-row decision traces or simulating positions.
Callable indicators used by vector cards must declare `execution="precompute"`
and be causal at every output row. Event signals carry scalar decision traces,
including indicator values and readiness; rejected decisions are recorded.
Position-scoped vector cards instead mark readiness candidates with
`metadata["position_scoped_lookback"] = True` and rescore rule
matches in the execution loop against the accepted first fill. This preserves
mixed market/position rules, signed weights, requirements, vetoes and overrides;
masking a final precomputed card result would not. Direct static
`card_signal_series()` rejects position-scoped cards unless explicitly requesting
internal candidates; candidates are not executable signals by themselves.

This separation does not extend an execution engine's risk-rule coverage.
In particular, the existing vector loop skips trailing stops and does not
run the phased portfolio exposure budget. Use the event engine to exercise
those settings in the reference strategy. Staged vector execution currently
uses the Python execution backend (`auto` falls back; strict Rust rejects it).
Position-scoped vector exits have the same execution-backend restriction,
with an explicit logged fallback or strict error rather than unbounded execution.

Existing `TradingStrategy` subclasses remain compatible: imperative signal
hooks, concrete `signal_cards`, and `generate_signals_from_cards()` still work.
Their concrete-card preparation/evaluation helpers now live in a compatibility
support class; generic lifecycle, execution and decision-trace recording remain
on `TradingStrategy`.

### Performance and verification

The shared indicator engine stores prepared card states only at changes in
matches, input readiness, or full-lookback readiness. NumPy detects these
boundaries and groups identical boolean states; scalar scoring runs once per
distinct state, rather than walking every candle in Python. Backward alignment
still returns the exact state at each decision time, and indicator snapshots
continue to use the latest completed candle, even between card-state changes.

Prepared event evaluation returns detached copies of the known card-payload
containers instead of recursively deep-copying scalar evidence. Mutating a
returned group, evaluation, match, or readiness mapping cannot alter cached
results. Strategies without scale-in cards also avoid the stage tracker's trade
queries. Staged strategies retain the inclusive, incremental fill-history
query, so a lot filled and closed between strategy ticks still advances its
stage correctly.

Run the offline benchmark from the repository root:

```bash
python -m scripts.bench_confluence_strategy \
  --rows 50000 --ticks 500 --repeats 3 --profile
```

Local medians before/after this optimization (Python 3.12.16, pandas 2.3.3,
NumPy 2.2.6, macOS arm64; three repetitions):

| Signal-generation workload | Before | After | Speedup |
|---|---:|---:|---:|
| Vector preparation, 50,000 native candles and three cards | 146.0 ms | 16.9 ms | 8.65x |
| 500 prepared, flat-position event decisions | 71.3 ms | 32.5 ms | 2.19x |

Before/after digests of the complete masks and event signals/decision traces
matched exactly. The benchmark reports timings, repeat parity, output digests,
and optional profiles. These are signal-generation measurements, not complete
backtest speedups: the event sample excludes provider ingestion and database/
broker execution, and the vector sample excludes trade execution and metrics.
Re-measure on the target workload; no Rust backend is required or enabled by
these optimizations. Existing native backend eligibility limits still apply.

### Manual card evaluation

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

## Named multi-group score cards

Use `ConfluenceScoreCard` when rules contribute to several groups, nested
thresholds should not double-count, or exceptional evidence can bypass normal
group thresholds. This is additive: existing `ConfluenceCard` definitions and
their primary/secondary semantics are unchanged.

```python
from investing_algorithm_framework import (
    AnyOf, ConfluenceScoreCard, ConfluenceScoreRule, EvaluationContext,
    Requirement, Rule, Threshold, condition,
)

entry_card = ConfluenceScoreCard(
    name="Z-score with confirmation",
    rules={
        "normal_z": ConfluenceScoreRule(
            condition("z_score", "lte", value=-2),
            group_weights={"primary": 1},
        ),
        "extreme_z": ConfluenceScoreRule(
            condition("z_score", "lte", value=-3),
            group_weights={"primary": 3},
        ),
        "rsi_confirmation": ConfluenceScoreRule(
            condition("rsi", "lte", value=30),
            group_weights={"secondary": 1},
        ),
    },
    group_aggregation={"primary": "max", "secondary": "sum"},
    group_thresholds={"primary": 1, "secondary": 1},
    override_triggers=AnyOf(
        Rule("extreme_z"), Threshold("primary", 3),
    ),
    requirements=(
        Requirement("Position available", condition("can_enter", "eq", value=True)),
    ),
)
result = entry_card.evaluate(EvaluationContext({
    "z_score": -3.2, "rsi": 50, "can_enter": True,
}))
assert result.qualified
assert result.score == 3
```

The framework evaluates prepared inputs; it does not calculate indicators.
An application can adapt its own indicator configurations into
`ConfluenceScoreRule(expression, group_weights)` without duplicating scoring.
Named cards work in `TradingStrategy.signal_cards`, decision traces, and compact
backtest records alongside legacy cards.

Qualification is:

```text
all requirements AND no veto AND (normal group thresholds OR override)
```

The normal path requires **every** configured group threshold, inclusively
with `>=`. An empty threshold mapping disables this path and requires an
override. Overrides bypass group thresholds only, never requirements, vetoes,
or external position/risk controls. `Rule(name)` references a raw observed
match, even if that rule earns zero points under `max`. `Threshold(group, value)`
compares the aggregated group score with `>=`. Combine these references and
ordinary conditions using `AnyOf`, `AllOf`, `Not`, or `AtLeast`. References are
allowed only in overrides, not rule predicates or mandatory gates.

Groups default to `sum`. With `max`, only the largest matching contribution
is credited; equal maxima credit the first rule in declaration order. Signed,
finite weights are supported: `max` selects among matched rules, including
negative weights, rather than introducing an unmatched zero. No matches yield
zero. A rule can contribute independently to multiple groups. The total is
the sum of group scores, not an additional qualification threshold.

For the example, normal Z plus RSI scores 2; extreme Z alone scores 3 and
qualifies by override; extreme Z plus RSI scores 4, not 5. The two overrides
are equivalent for this configuration but illustrate both reference types.
Rule predicates are evaluated once per scalar evaluation regardless of how
many groups or override references use them.

Results preserve raw matches and credited points separately. Score groups
have category `"score"`; an overridden, failed group threshold remains visible
without being treated as a mandatory secondary rejection. `normal_path` and
`override_path` evidence explain qualification. Requirements and vetoes retain
their ordinary evidence categories.

Definitions round-trip through `ConfluenceScoreCard.to_dict()` and
`ConfluenceScoreCard.from_dict()` using `confluence_score_card_version: 1`.
The explicit `rule_order` list preserves tie attribution through sorted JSON
and canonical backtest records. Do not remove it when transforming definitions.
Unknown references, invalid weights, unsupported aggregation, and thresholds
above the maximum possible score are rejected at construction.

`evaluate_series(frame, backend="python")` and `backend="auto"` use the pandas
evaluator. All configured rule, requirement, veto, and override inputs must be
available, including when an override could otherwise qualify. Crossings also
require the previous bar. Missing inputs fail closed.
Explicit `backend="rust"` raises `NativeConfluenceUnsupported`: named-card
semantics are not implemented in the native kernel yet. Existing legacy native
evaluation is unchanged.

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
