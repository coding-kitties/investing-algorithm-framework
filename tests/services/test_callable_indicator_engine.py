"""Caller-controlled indicator execution and native-history contracts."""
from dataclasses import replace
import pickle
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import polars as pl
import pytest
from pandas.testing import assert_frame_equal

from investing_algorithm_framework import (
    AllOf, AnyOf, AtLeast, BacktestDateRange, ConfluenceScoreCard, ConfluenceScoreConfig, DataSource,
    EvaluationContext, IndicatorConfig, IndicatorEngine, IndicatorRule,
    Not, Requirement, Rule, Schedule, SignalSide, Threshold, TradingStrategy, Veto, condition,
)
from investing_algorithm_framework.services.strategy_phases import (
    EvaluateIndicatorsPhase, PhaseState,
)
from investing_algorithm_framework.infrastructure.services.backtesting.event_backtest_service import EventBacktestService


def source(identifier="prices", timeframe="1h"):
    return DataSource(identifier=identifier, symbol="BTC/EUR", data_type="ohlcv",
                      time_frame=timeframe, warmup_window=100)


def prices(backend="pandas", n=8, timeframe="1h"):
    index = pd.date_range("2024-01-01", periods=n, freq=timeframe, tz="UTC")
    frame = pd.DataFrame({
        "Open": np.arange(n, dtype=float), "High": np.arange(n) + 3.,
        "Low": np.arange(n) - 2., "Close": np.arange(n) + 1.,
        "Volume": np.ones(n), "custom_field": np.arange(n) + 50.,
    }, index=index)
    return pl.from_pandas(frame.rename_axis("Datetime").reset_index()) if backend == "polars" else frame


def custom(frame, factor=3):
    if isinstance(frame, pl.DataFrame):
        return frame.with_columns(
            (pl.col("Close").cum_sum() * factor + pl.col("custom_field")).alias("custom"),
        )
    frame["custom"] = frame.Close.cumsum() * factor + frame.custom_field
    return frame


def config(**kwargs):
    return IndicatorConfig(
        **({"id": "custom", "data_source": "prices", "calculate": custom,
            "parameters": {"factor": 3}, "output_columns": ["custom"],
            "minimum_history": 2} | kwargs),
    )


def card(**kwargs):
    return ConfluenceScoreConfig(
        id="entry", rules={"match": IndicatorRule(
            "custom", threshold=60, group_weights={"primary": 1},
            output_column="custom", lookback_period=2,
        )}, group_thresholds={"primary": 1}, **kwargs,
    )


def window(frame, start, stop):
    return frame.slice(start, stop - start) if isinstance(frame, pl.DataFrame) else frame.iloc[start:stop]


@pytest.mark.parametrize("prepared", [False, True])
def test_real_event_preparation_is_run_local_and_respects_callable_opt_in(prepared):
    raw = prices()
    calls = {"prepared": [], "decision": []}

    def prepared_function(frame, factor):
        calls["prepared"].append(len(frame))
        return custom(frame, factor)

    def decision_function(frame, factor):
        calls["decision"].append(len(frame))
        return custom(frame, factor)

    configs = [config(id="decision", calculate=decision_function)]
    if prepared:
        configs.append(config(
            id="prepared", calculate=prepared_function, execution="precompute",
        ))
    strategy = TradingStrategy(
        schedule=Schedule.every(1, "hour"), indicator_configs=configs, data_sources=[source()],
    )
    provider = Mock()
    provider.get_backtest_data.return_value = raw
    service = EventBacktestService(provider, None, None, None, None, None, None, None)
    date_range = BacktestDateRange(
        name="window", start_date=raw.index[4].to_pydatetime(),
        end_date=raw.index[-1].to_pydatetime(),
    )
    algorithm = SimpleNamespace(strategies=[strategy])
    service.prepare_indicators(algorithm, date_range)
    first_engine = strategy._indicator_engine
    assert calls == {"prepared": [len(raw)] if prepared else [], "decision": []}
    if prepared:
        provider.get_backtest_data.assert_called_once_with(
            strategy.data_sources[0],
            start_date=strategy.data_sources[0].create_start_date_data(date_range.start_date),
            end_date=date_range.end_date,
        )
    else:
        provider.get_backtest_data.assert_not_called()
    observed = first_engine.evaluate({"prices": raw.iloc[:6]}, raw.index[5])
    assert calls["decision"] == [5]
    assert observed.values["decision"]["custom"] == custom(raw.iloc[:5].copy()).iloc[-1]["custom"]
    service.prepare_indicators(algorithm, date_range)
    assert strategy._indicator_engine is not first_engine
    strategy._indicator_engine.evaluate({"prices": raw.iloc[:5]}, raw.index[4])
    assert calls["decision"] == [5, 4]
    assert calls["prepared"] == ([len(raw), len(raw)] if prepared else [])


def test_callable_configuration_export_does_not_serialize_executable_code():
    with pytest.raises(TypeError, match="Callable indicators"):
        config().to_dict()


def test_worker_pickle_preserves_callable_configs_cards_and_immutability():
    cfg = config(execution="precompute")
    declared_card = card()
    copied_config, copied_card, compiled = pickle.loads(pickle.dumps((
        cfg, declared_card, declared_card.compile("entry"),
    )))
    assert copied_config == cfg
    assert copied_config.calculate is custom
    assert copied_card == declared_card
    assert compiled.to_dict() == declared_card.compile("entry").to_dict()
    with pytest.raises(TypeError):
        copied_config.parameters["factor"] = 4
    with pytest.raises(TypeError):
        copied_card.rules["new"] = declared_card.rules["match"]
    engine = IndicatorEngine([copied_config], [copied_card], [source()])
    frame = prices()
    result = engine.prepare({"prices": frame}).evaluate({}, frame.index[-1])
    assert result.ready["custom"]


@pytest.mark.parametrize("field_name", ["required_rules", "blocking_rules", "gates"])
@pytest.mark.parametrize("names", [
    None, "match", {"match"}, {"match": True}, [1], [""], [" match"],
    ["match "], ["unknown"], ["match", "match"],
])
def test_named_card_gate_validation(field_name, names):
    with pytest.raises(ValueError, match=field_name):
        card(**{field_name: names})


@pytest.mark.parametrize("field_name", ["blocking_rules", "gates"])
def test_named_card_gates_cannot_require_and_block_the_same_rule(field_name):
    with pytest.raises(ValueError, match="both required and blocking"):
        card(required_rules=["match"], **{field_name: ["match"]})


@pytest.mark.parametrize("field_name,gate_type,prefix,gate_field", [
    ("required_rules", Requirement, "required_rule", "requirements"),
    ("blocking_rules", Veto, "blocking_rule", "vetoes"),
    ("gates", Veto, "blocking_rule", "vetoes"),
])
def test_named_card_gates_reject_evidence_name_collisions(
    field_name, gate_type, prefix, gate_field,
):
    with pytest.raises(ValueError, match="gate names are already configured"):
        card(**{
            field_name: ["match"],
            gate_field: (gate_type(
                f"{prefix}:match", condition("match", "eq", value=True),
            ),),
        })


def test_named_card_gates_preserve_explicit_gates_serialization_and_pickle():
    names = ["match"]
    declared = card(
        required_rules=names,
        requirements=(Requirement(
            "explicit_required", condition("match", "eq", value=True),
        ),),
        vetoes=(Veto(
            "explicit_veto", condition("match", "eq", value=False),
        ),),
    )
    names.clear()
    assert declared.required_rules == ("match",)
    assert declared.blocking_rules == ()
    compiled = declared.compile("entry")
    restored = ConfluenceScoreCard.from_dict(compiled.to_dict())
    copied, copied_compiled = pickle.loads(pickle.dumps((declared, compiled)))
    assert copied == declared
    assert copied_compiled == restored == compiled
    assert [gate.name for gate in compiled.requirements] == [
        "explicit_required", "required_rule:match",
    ]
    assert [gate.name for gate in compiled.vetoes] == ["explicit_veto"]
    for matched in (False, True):
        context = EvaluationContext({"match": matched})
        assert restored.evaluate(context).to_dict() == compiled.evaluate(context).to_dict()


def test_gates_alias_preserves_existing_blocker_behavior_and_deduplicates():
    names = ["match"]
    declared = card(gates=names)
    names.clear()
    assert declared.gates == ("match",)
    assert pickle.loads(pickle.dumps(declared)) == declared
    legacy = card(blocking_rules=["match"])
    combined = card(gates=["match"], blocking_rules=["match"])
    compiled = declared.compile("entry")
    assert compiled.to_dict() == legacy.compile("entry").to_dict()
    assert compiled.to_dict() == combined.compile("entry").to_dict()
    assert len(compiled.vetoes) == 1
    for matched in (False, True):
        context = EvaluationContext({"match": matched})
        assert compiled.evaluate(context).to_dict() == legacy.compile("entry").evaluate(context).to_dict()


def directional_card(side, **changes):
    is_long = side in (SignalSide.OPEN_LONG, SignalSide.SCALE_IN)
    return ConfluenceScoreConfig(**({
        "id": side.value,
        "side": side,
        "scale_in_stage": 0 if side is SignalSide.SCALE_IN else None,
        "rules": {
            "z_trigger": IndicatorRule(
                "research", -2 if is_long else 2, {"primary": 1},
                output_column="zscore", comparison="lt" if is_long else "gt",
            ),
            "direction_allowed": IndicatorRule(
                "research", 1 if is_long else 0,
                output_column="supertrend_trend", comparison="eq",
            ),
            "blocked": IndicatorRule(
                "research", 1, group_weights=None,
                output_column="blocked", comparison="eq",
            ),
            "confirmation": IndicatorRule(
                "research", 1, {"confirmation": 1},
                output_column="confirmation", comparison="eq",
            ),
        },
        "group_thresholds": {"primary": 1},
        "override_triggers": Rule("confirmation"),
        "required_rules": ["z_trigger", "direction_allowed"],
        "blocking_rules": ["blocked"],
    } | changes))


@pytest.mark.parametrize("side", [
    SignalSide.OPEN_LONG, SignalSide.OPEN_SHORT, SignalSide.SCALE_IN,
])
@pytest.mark.parametrize("triggered", [False, True])
@pytest.mark.parametrize("direction_allowed", [False, True])
@pytest.mark.parametrize("blocked", [False, True])
@pytest.mark.parametrize("blocker_field", ["blocking_rules", "gates"])
def test_named_card_gates_are_mandatory_even_with_overrides(
    side, triggered, direction_allowed, blocked, blocker_field,
):
    changes = (
        {"blocking_rules": [], "gates": ["blocked"]}
        if blocker_field == "gates" else {}
    )
    declared = directional_card(side, **changes)
    compiled = declared.compile(declared.id)
    matches = {
        "z_trigger": triggered, "direction_allowed": direction_allowed,
        "blocked": blocked, "confirmation": True,
    }
    result = compiled.evaluate(EvaluationContext(matches))
    assert result.primary_triggered
    assert result.qualified == (triggered and direction_allowed and not blocked)
    assert result.requirements_passed == (triggered and direction_allowed)
    assert result.veto_triggered == blocked
    assert result.score == float(triggered) + 1
    assert [(item.name, item.matched) for item in result.evaluations
            if item.category in ("requirement", "veto")] == [
        ("required_rule:z_trigger", triggered),
        ("required_rule:direction_allowed", direction_allowed),
        ("blocking_rule:blocked", blocked),
    ]
    series = compiled.evaluate_series(pd.DataFrame([matches]))
    assert series["qualified"].tolist() == [result.qualified]
    assert series["score"].tolist() == [result.score]
    copied = pickle.loads(pickle.dumps(declared))
    assert copied.required_rules == declared.required_rules
    assert copied.blocking_rules == declared.blocking_rules
    assert copied.gates == declared.gates
    assert copied.compile(declared.id).evaluate(
        EvaluationContext(matches),
    ).to_dict() == result.to_dict()


def research_outputs(frame):
    return frame


@pytest.mark.parametrize("weight_settings", [
    {}, {"group_weights": None}, {"group_weights": {}},
])
def test_supertrend_bearish_gate_blocks_long_without_extra_entry_filters(weight_settings):
    frame = prices(n=4)
    frame["zscore"] = -3.0
    frame["supertrend_trend"] = [1.0, 0.0, np.nan, 1.0]
    declaration = ConfluenceScoreConfig(
        id="long_entry", side=SignalSide.OPEN_LONG,
        rules={
            "oversold": IndicatorRule(
                "research", -2, {"primary": 1},
                output_column="zscore",
            ),
            "supertrend_bearish": IndicatorRule(
                "research", 0, comparison="eq",
                output_column="supertrend_trend", **weight_settings,
            ),
        },
        group_thresholds={"primary": 1},
        gates=["supertrend_bearish"],
    )
    engine = IndicatorEngine([
        config(
            id="research", calculate=research_outputs, parameters={},
            minimum_history=1, output_columns=["zscore", "supertrend_trend"],
            execution="precompute",
        ),
    ], [declaration], [source()]).prepare({"prices": frame})
    decisions = frame.index + pd.Timedelta(hours=1)
    assert engine.card_signal_series(decisions)["long_entry"].tolist() == [
        True, False, False, True,
    ]
    assert dict(declaration.rules["supertrend_bearish"].group_weights) == {}
    with pytest.raises(TypeError):
        declaration.rules["supertrend_bearish"].group_weights["dummy"] = 1
    compiled = declaration.compile("entry")
    assert set(compiled.group_aggregation) == {"primary"}
    for i, decision in enumerate(decisions):
        evaluation = engine.evaluate({}, decision)
        snapshot = engine.confluence_snapshot(evaluation)[0]
        gate = next(
            item for item in snapshot["evaluations"]
            if item["name"] == "supertrend_bearish"
        )
        assert gate["points"] == gate["weight"] == 0
        assert gate["group"] is None
        assert gate["output_column"] == "supertrend_trend"
        assert gate["value"] == (None if i == 2 else frame["supertrend_trend"].iloc[i])
        assert snapshot["maximum_score"] == 1
    inspection = engine.get_confluence_score_cards("BTC")[0]
    assert "Unweighted rules" in str(inspection)
    assert "supertrend_bearish: research.supertrend_trend == 0" in str(inspection)
    assert pickle.loads(pickle.dumps(declaration)) == declaration


@pytest.mark.parametrize("weights", [[], "", 1, False, {"p": np.nan}, {"p": True}])
def test_optional_indicator_weights_still_reject_invalid_values(weights):
    with pytest.raises(ValueError):
        IndicatorRule("research", 0, group_weights=weights)


@pytest.mark.parametrize("policy", [None, "", "paths", True, 1])
def test_invalid_readiness_policy_is_rejected(policy):
    with pytest.raises(ValueError, match="readiness_policy"):
        card(readiness_policy=policy)


@pytest.mark.parametrize("policy", ["all_rules", "qualification_paths"])
@pytest.mark.parametrize("backend", ["pandas", "polars"])
@pytest.mark.parametrize("execution", ["per_decision", "precompute"])
@pytest.mark.parametrize("scoped", [False, True])
def test_independent_bearish_exit_with_unready_position_scoped_zscore(
    policy, backend, execution, scoped,
):
    frame = prices(n=9)
    frame["zscore"] = [np.nan, np.nan, np.nan, -1, -1, np.nan, 1, -1, 1]
    frame["supertrend_trend"] = [1, 0, 1, 1, 1, 0, np.nan, 0, 1]
    declaration = ConfluenceScoreConfig(
        id="exit", side=SignalSide.CLOSE_LONG,
        rules={
            "z_exit": IndicatorRule(
                "research", 0, {"primary": 1}, output_column="zscore",
                comparison="ge", lookback_period=14,
                lookback_scope="position" if scoped else "market",
            ),
            "bearish": IndicatorRule(
                "research", 0, output_column="supertrend_trend", comparison="eq",
            ),
        },
        group_thresholds={"primary": 1},
        override_triggers=Rule("bearish"),
        readiness_policy=policy,
    )
    cfg = config(
        id="research", calculate=research_outputs, parameters={}, minimum_history=1,
        output_columns=["zscore", "supertrend_trend"], execution=execution,
    )
    raw = (
        pl.from_pandas(frame.rename_axis("Datetime").reset_index())
        if backend == "polars" else frame
    )
    event = IndicatorEngine([cfg], [declaration], [source()])
    prepared = IndicatorEngine([cfg], [declaration], [source()]).prepare({"prices": raw})
    decisions = frame.index + pd.Timedelta(hours=1)
    expected = [
        False, policy == "qualification_paths", False, False, False,
        policy == "qualification_paths", policy == "qualification_paths", True, True,
    ]
    candidates = (
        prepared.card_signal_series(decisions, position_scoped_candidates=True)["exit"]
        if execution == "precompute" else None
    )
    for i, decision in enumerate(decisions):
        prefix = window(raw, 0, i + 1)
        options = {"position_opened_at": {"exit": frame.index[0]}} if scoped else {}
        observed = event.evaluate({"prices": prefix}, decision, **options)
        cached = prepared.evaluate({"prices": prefix}, decision, **options)
        assert observed.cards == cached.cards
        payload = observed.cards["exit"]
        assert bool(payload["passed"] and payload["ready"]) == expected[i], i
        if i in (1, 5):
            assert not observed.rule_readiness["exit"]["z_exit"]
            assert observed.rule_readiness["exit"]["bearish"]
        snapshot = prepared.confluence_snapshot(cached)[0]
        decision_entry = next(
            entry for entry in snapshot["decision_trace"]["entries"]
            if entry["group"] == "decision" and entry["name"] == "decision"
        )
        assert decision_entry["value"] == ("QUALIFIED" if expected[i] else "REJECTED")
        if candidates is not None:
            emitted = bool(candidates.iloc[i]) and prepared.position_scoped_exit_signal(
                decision, frame.index[0], side=SignalSide.CLOSE_LONG,
            )
            assert emitted == expected[i]
    restored = pickle.loads(pickle.dumps(declaration))
    assert restored.readiness_policy == policy
    assert restored == declaration
    inspection = prepared.get_confluence_score_cards("BTC")[0]
    assert f"Readiness: {policy}" in str(inspection)
    if scoped:
        with pytest.raises(ValueError, match="actual entry fill"):
            prepared.evaluate_card("exit", decisions[-1])


@pytest.mark.parametrize("expression,a,b,ready_a,ready_b,expected", [
    (Rule("a"), True, False, True, False, True),
    (Rule("a"), False, False, False, True, False),
    (Not(Rule("a")), False, False, False, True, False),
    (Not(Rule("a")), False, False, True, True, True),
    (AnyOf(Rule("a"), Rule("b")), True, False, True, False, True),
    (AnyOf(Rule("a"), Not(Rule("b"))), False, False, True, False, False),
    (AllOf(Rule("a"), Rule("b")), True, False, True, False, False),
    (AllOf(Rule("a"), Not(Rule("b"))), True, False, True, False, False),
    (AtLeast(1, (Rule("a"), Rule("b"))), True, False, True, False, True),
    (AtLeast(2, (Rule("a"), Rule("b"))), True, False, True, False, False),
    (Not(AllOf(Rule("a"), Rule("b"))), False, False, True, False, True),
    (condition("a", "eq", value=False), False, False, False, True, False),
    (condition("a", "eq", value=False), False, False, True, False, True),
    (condition("a", "eq", reference="b"), False, False, True, False, False),
    (AnyOf(condition("a", "eq", value=True), Rule("b")), True, False, True, False, True),
])
def test_path_readiness_handles_boolean_override_expressions_without_missing_negation(
    expression, a, b, ready_a, ready_b, expected,
):
    declaration = ConfluenceScoreConfig(
        id="entry",
        rules={
            "normal": IndicatorRule("custom", 1, {"primary": 1}, output_column="custom"),
            "a": IndicatorRule("custom", 1, output_column="custom"),
            "b": IndicatorRule("custom", 1, output_column="custom"),
        },
        group_thresholds={"primary": 1}, override_triggers=expression,
        readiness_policy="qualification_paths",
    )
    engine = IndicatorEngine([config()], [declaration], [source()])
    readiness = {"normal": False, "a": ready_a, "b": ready_b}
    payload = engine._score_card(
        "entry", {"normal": False, "a": a, "b": b}, readiness, readiness,
    )
    assert bool(payload["passed"] and payload["ready"]) == expected


@pytest.mark.parametrize("gate_kind", ["gates", "required_rules", "requirements", "vetoes"])
@pytest.mark.parametrize("ready,matched,expected", [
    (False, False, False), (False, True, False),
    (True, False, True), (True, True, False),
])
def test_ready_override_never_bypasses_unready_or_blocking_hard_gates(
    gate_kind, ready, matched, expected,
):
    allowed = not matched if gate_kind in ("required_rules", "requirements") else matched
    settings = (
        {gate_kind: ["guard"]} if gate_kind in ("gates", "required_rules") else
        {gate_kind: ((
            Requirement if gate_kind == "requirements" else Veto
        )("hard_guard", condition("guard", "eq", value=True)),)}
    )
    declaration = ConfluenceScoreConfig(
        id="entry",
        rules={
            "normal": IndicatorRule("custom", 1, {"primary": 1}, output_column="custom"),
            "override": IndicatorRule("custom", 1, output_column="custom"),
            "guard": IndicatorRule("custom", 1, output_column="custom"),
        },
        group_thresholds={"primary": 1}, override_triggers=Rule("override"),
        readiness_policy="qualification_paths", **settings,
    )
    engine = IndicatorEngine([config()], [declaration], [source()])
    readiness = {"normal": False, "override": True, "guard": ready}
    payload = engine._score_card(
        "entry", {"normal": False, "override": True, "guard": allowed},
        readiness, readiness,
    )
    assert bool(payload["passed"] and payload["ready"]) == expected


@pytest.mark.parametrize("aggregation", ["sum", "max"])
@pytest.mark.parametrize("policy", ["all_rules", "qualification_paths"])
def test_normal_and_threshold_override_readiness_never_ignores_unknown_signed_weights(
    aggregation, policy,
):
    declaration = ConfluenceScoreConfig(
        id="entry",
        rules={
            "positive": IndicatorRule("custom", 1, {"primary": 1}, output_column="custom"),
            "negative": IndicatorRule("custom", 1, {"primary": -2}, output_column="custom"),
            "unrelated": IndicatorRule("custom", 1, output_column="custom"),
        },
        group_aggregation={"primary": aggregation}, group_thresholds={"primary": 0},
        override_triggers=Threshold("primary", 0), readiness_policy=policy,
    )
    engine = IndicatorEngine([config()], [declaration], [source()])
    for matches, readiness, expected in (
        ({"positive": True, "negative": False, "unrelated": False},
         {"positive": True, "negative": False, "unrelated": True}, False),
        ({"positive": True, "negative": False, "unrelated": False},
         {"positive": True, "negative": True, "unrelated": False},
         policy == "qualification_paths"),
    ):
        payload = engine._score_card("entry", matches, readiness, readiness)
        assert bool(payload["passed"] and payload["ready"]) == expected


@pytest.mark.parametrize("execution", ["per_decision", "precompute"])
def test_ready_override_uses_its_own_rule_delay_and_respects_card_delay(execution):
    frame = prices(n=4)
    frame["zscore"] = np.nan
    frame["supertrend_trend"] = 0
    cfg = config(
        id="research", calculate=research_outputs, parameters={}, minimum_history=1,
        output_columns=["zscore", "supertrend_trend"], execution=execution,
    )
    declaration = ConfluenceScoreConfig(
        id="entry",
        rules={
            "normal": IndicatorRule(
                "research", 0, {"primary": 1}, output_column="zscore",
                initial_delay=5,
            ),
            "bearish": IndicatorRule(
                "research", 0, output_column="supertrend_trend",
                comparison="eq", initial_delay=1,
            ),
        },
        group_thresholds={"primary": 1}, override_triggers=Rule("bearish"),
        readiness_policy="qualification_paths", initial_delay=1,
    )
    event = IndicatorEngine([cfg], [declaration], [source()])
    prepared = IndicatorEngine([cfg], [declaration], [source()]).prepare({"prices": frame})
    decisions = frame.index + pd.Timedelta(hours=1)
    expected = [False, False, True, True]
    for i, decision in enumerate(decisions):
        prefix = frame.iloc[:i + 1]
        observed = event.evaluate({"prices": prefix}, decision).cards["entry"]
        cached = prepared.evaluate({"prices": prefix}, decision).cards["entry"]
        assert observed == cached
        assert bool(observed["passed"] and observed["ready"]) == expected[i]
    if execution == "precompute":
        assert prepared.card_signal_series(decisions)["entry"].tolist() == expected


@pytest.mark.parametrize("backend", ["pandas", "polars"])
@pytest.mark.parametrize("execution", ["per_decision", "precompute"])
@pytest.mark.parametrize("blocker_field", ["blocking_rules", "gates"])
def test_named_directional_gates_event_prepared_vector_and_unrestricted_exits(
    backend, execution, blocker_field,
):
    frame = prices(n=11)
    frame["zscore"] = [-3, -3, -3, 3, 3, -3, -3, 0, 0, -2, -3]
    frame["supertrend_trend"] = [1, 1, 0, 0, 1, np.nan, 1, 0, 1, 1, 1]
    frame["blocked"] = [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, np.nan]
    frame["confirmation"] = 1
    expected = {
        "open_long": [False, True, False, False, False, False, False, False, False, False, False],
        "open_short": [False, False, False, True, False, False, False, False, False, False, False],
        "scale_in": [False, True, False, False, False, False, False, False, False, False, False],
        "close_long": [False, False, False, True, True, False, False, True, True, False, False],
    }
    cfg = config(
        id="research", calculate=research_outputs, parameters={},
        output_columns=["zscore", "supertrend_trend", "blocked", "confirmation"],
        execution=execution,
    )
    declarations = [
        directional_card(
            side, **({"blocking_rules": [], "gates": ["blocked"]}
                     if blocker_field == "gates" else {}),
        )
        for side in (
            SignalSide.OPEN_LONG, SignalSide.OPEN_SHORT, SignalSide.SCALE_IN,
        )
    ] + [
        ConfluenceScoreConfig(
            id="close_long", side=SignalSide.CLOSE_LONG,
            rules={"reverted": IndicatorRule(
                "research", -0.2, {"primary": 1},
                output_column="zscore", comparison="ge",
            )}, group_thresholds={"primary": 1},
        ),
    ]
    raw = (
        pl.from_pandas(frame.rename_axis("Datetime").reset_index())
        if backend == "polars" else frame
    )
    event = IndicatorEngine([cfg], declarations, [source()])
    prepared = IndicatorEngine([cfg], declarations, [source()]).prepare({"prices": raw})
    decisions = frame.index + pd.Timedelta(hours=1)
    for i, stamp in enumerate(decisions):
        prefix = window(raw, 0, i + 1)
        observed = event.evaluate({"prices": prefix}, stamp)
        cached = prepared.evaluate({"prices": prefix}, stamp)
        assert observed.cards == cached.cards
        for name, flags in expected.items():
            payload = observed.cards[name]
            assert (payload["passed"] and payload["ready"]) == flags[i], (name, i)
    if execution == "precompute":
        for name, flags in expected.items():
            assert prepared.card_signal_series(decisions)[name].tolist() == flags
    inspection = prepared.get_confluence_score_cards("BTC")[0]
    assert inspection.configuration.required_rules == (
        "z_trigger", "direction_allowed",
    )
    assert getattr(inspection.configuration, blocker_field) == ("blocked",)
    assert "required_rule:direction_allowed" in str(inspection)
    assert "blocking_rule:blocked" in str(inspection)


@pytest.mark.parametrize("backend", ["pandas", "polars"])
@pytest.mark.parametrize("execution", ["per_decision", "precompute"])
@pytest.mark.parametrize("prepared", [False, True])
def test_callable_backend_history_parity_and_original_columns(backend, execution, prepared):
    raw = prices(backend)
    before = raw.clone() if backend == "polars" else raw.copy(deep=True)
    calls = []

    def calculate(frame, factor):
        assert isinstance(frame, type(raw))
        assert {"High", "Low", "Close", "Volume", "custom_field"} <= set(frame.columns)
        if backend == "polars":
            assert frame.schema["Datetime"] == raw.schema["Datetime"]
        calls.append(len(frame))
        return custom(frame, factor)

    cfg = config(calculate=calculate, execution=execution)
    engine = IndicatorEngine([cfg], [card()], [source()])
    if prepared:
        engine.prepare({"prices": raw})
        assert calls == ([len(raw)] if execution == "precompute" else [])
    index = pd.date_range("2024-01-01", periods=len(raw), freq="1h", tz="UTC")
    for i, stamp in enumerate(index):
        for offset in (1, 1.25):
            result = engine.evaluate(
                {"prices": window(raw, max(0, i - 2), i + 1)},
                stamp + pd.Timedelta(hours=offset),
            )
            if i == 0:
                assert not result.ready["custom"]
                assert np.isnan(result.values["custom"]["custom"])
            else:
                assert result.ready["custom"]
                assert result.values["custom"]["custom"] == 3 * sum(range(1, i + 2)) + 50 + i
                assert result.cards["entry"]["passed"] == (i <= 2)
    if execution == "per_decision":
        assert calls == [length for length in range(2, len(raw) + 1) for _ in range(2)]
    elif prepared:
        assert calls == [len(raw)]
    else:
        assert calls == list(range(2, len(raw) + 1))
    if backend == "polars":
        assert before.equals(raw)
    else:
        assert_frame_equal(before, raw)


@pytest.mark.parametrize("backend", ["pandas", "polars"])
def test_prepared_default_callable_is_fresh_and_mixed_cards_are_not_cached(backend):
    calls = []

    def stateful(frame):
        calls.append(len(frame))
        value = 1 if len(calls) == 1 else -1
        if isinstance(frame, pl.DataFrame):
            return frame.with_columns(pl.lit(value).alias("fresh"))
        return frame.assign(fresh=value)

    configs = [
        config(id="fresh", calculate=stateful, parameters={}, output_columns=["fresh"], minimum_history=1),
        config(execution="precompute"),
        IndicatorConfig("legacy", "ema", period=1, timeframe="1h", data_source="prices"),
    ]
    declaration = ConfluenceScoreConfig(id="mixed", rules={
        "fresh": IndicatorRule("fresh", 0, {"a": 1}, comparison="gt", output_column="fresh"),
        "static": IndicatorRule("custom", 0, {"a": 1}, comparison="gt", output_column="custom"),
    }, group_thresholds={"a": 2})
    raw = prices(backend)
    engine = IndicatorEngine(configs, [declaration], [source()]).prepare({"prices": raw})
    assert calls == []
    now = pd.Timestamp("2024-01-01 03:00", tz="UTC")
    first = engine.evaluate({}, now)
    second = engine.evaluate({}, now)
    assert calls == [3, 3]
    assert first.cards["mixed"]["passed"]
    assert not second.cards["mixed"]["passed"]
    assert first.values["legacy"]["value"] == 3


def test_stateful_distinct_declarations_are_not_deduplicated():
    calls = []

    def stateful(frame):
        calls.append(len(frame))
        return frame.assign(custom=len(calls))

    engine = IndicatorEngine(
        [config(id="a", calculate=stateful, parameters={}),
         config(id="b", calculate=stateful, parameters={})], [], [source()],
    )
    result = engine.evaluate({"prices": prices()}, pd.Timestamp("2024-01-01 03:00", tz="UTC"))
    assert result.values == {"a": {"custom": 1}, "b": {"custom": 2}}
    assert calls == [3, 3]


@pytest.mark.parametrize("kwargs,error", [
    ({"calculate": 5}, TypeError),
    ({"parameters": []}, TypeError),
    ({"output_columns": []}, ValueError),
    ({"output_columns": [""]}, ValueError),
    ({"output_columns": ["  "]}, ValueError),
    ({"output_columns": ["custom", "custom"]}, ValueError),
    ({"minimum_history": 0}, ValueError),
    ({"minimum_history": True}, ValueError),
    ({"history": "rolling"}, ValueError),
    ({"execution": "auto"}, ValueError),
])
def test_callable_config_validation(kwargs, error):
    with pytest.raises(error):
        config(**kwargs)


@pytest.mark.parametrize("backend", ["pandas", "polars"])
@pytest.mark.parametrize("violation", ["series", "missing", "length", "order", "timestamps", "text", "bool", "duplicates"])
def test_callable_output_schema_and_alignment_failures(backend, violation):
    def invalid(frame):
        output = custom(frame)
        if backend == "polars":
            if violation == "series":
                return output["custom"]
            if violation == "missing":
                return output.drop("custom")
            if violation == "length":
                return output.head(1)
            if violation == "order":
                return output.reverse()
            if violation == "timestamps":
                return output.with_columns(pl.col("Datetime") + pl.duration(minutes=1))
            if violation == "duplicates":
                return pl.concat([output.head(1)] * len(output))
            return output.with_columns(pl.lit("bad" if violation == "text" else True).alias("custom"))
        if violation == "series":
            return output.custom
        if violation == "missing":
            return output.drop(columns="custom")
        if violation == "length":
            return output.iloc[:1]
        if violation == "order":
            return output.iloc[::-1]
        if violation == "timestamps":
            output.index += pd.Timedelta(minutes=1)
            return output
        if violation == "duplicates":
            return pd.concat([output.iloc[:1]] * len(output))
        return output.assign(custom="bad" if violation == "text" else True)

    engine = IndicatorEngine([config(calculate=invalid, parameters={})], [], [source()])
    with pytest.raises(ValueError, match="Indicator custom source prices") as exc:
        engine.evaluate({"prices": prices(backend)}, pd.Timestamp("2024-01-01 04:00", tz="UTC"))
    assert exc.value.__cause__ is not None
    expected_message = {
        "series": "DataFrame", "missing": "missing declared columns",
        "length": "length", "order": "unique and increasing",
        "timestamps": "timestamps/order", "text": "numeric", "bool": "numeric",
        "duplicates": "unique and increasing",
    }[violation]
    assert expected_message in str(exc.value.__cause__)


def test_callable_exception_chaining_and_readiness_does_not_invoke_too_early():
    error = RuntimeError("custom calculation failed")
    calls = []

    def broken(frame):
        calls.append(len(frame))
        raise error

    engine = IndicatorEngine([config(calculate=broken, parameters={})], [card()], [source()])
    first = engine.evaluate({"prices": prices()}, pd.Timestamp("2024-01-01 01:00", tz="UTC"))
    assert not calls
    assert not first.ready["custom"]
    assert not first.cards["entry"]["passed"]
    second = engine.evaluate({}, pd.Timestamp("2024-01-01 02:00", tz="UTC"))
    assert not second.ready["custom"]
    assert not calls
    with pytest.raises(ValueError, match="custom.*prices") as exc:
        engine.evaluate({"prices": prices()}, pd.Timestamp("2024-01-01 02:00", tz="UTC"))
    assert exc.value.__cause__ is error
    assert calls == [2]


def test_card_list_binding_and_legacy_replace_compatibility():
    cfg = config()
    with pytest.raises(ValueError, match="non-empty ids"):
        IndicatorEngine([cfg], [replace(card(), id=None)], [source()])
    with pytest.raises(ValueError, match="Duplicate card"):
        IndicatorEngine([cfg], [card(), card()], [source()])
    for output in (None, "other"):
        rule = IndicatorRule("custom", 0, {"a": 1}, output_column=output)
        with pytest.raises(ValueError, match="explicit output|Unknown"):
            IndicatorEngine([cfg], [ConfluenceScoreConfig(
                id="bad", rules={"r": rule}, group_thresholds={"a": 1},
            )], [source()])
    legacy = IndicatorRule("macd", 0, {"a": 1}, output="signal")
    assert replace(legacy, output="histogram").selected_output == "histogram"


def test_strategy_preserves_card_list_and_engine_override():
    class Strategy(TradingStrategy):
        schedule = Schedule.every(1, "hour")
        data_sources = [source()]
        indicator_configs = [config()]
        confluence_cards = [card()]

    first, second = Strategy(), Strategy()
    assert isinstance(first.indicator_configs, list)
    assert first.indicator_configs is not second.indicator_configs
    assert isinstance(first.confluence_cards, list)
    assert first.confluence_cards == Strategy.confluence_cards
    assert first.confluence_cards is not second.confluence_cards
    engine = IndicatorEngine(first.indicator_configs, first.confluence_cards, first.data_sources)
    first._indicator_engine = engine
    state = PhaseState(first, SimpleNamespace(), {"prices": prices()},
                       pd.Timestamp("2024-01-01 02:00", tz="UTC"))
    EvaluateIndicatorsPhase().run(state)
    assert first._indicator_engine is engine
    assert state.data["indicators"].ready["custom"]


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("execution", ["per_decision", "precompute"])
def test_callable_native_lookbacks_are_independent_across_timeframes(prepared, execution):
    def identity(frame):
        return frame.assign(custom=frame.Close)

    fast, slow = prices(n=5), prices(n=3, timeframe="2h")
    fast["Close"] = [1., 9., 9., np.nan, 9.]
    slow["Close"] = [1., 9., 9.]
    configs = [config(id=identifier, data_source=identifier, calculate=identity,
                      parameters={}, minimum_history=1, execution=execution)
               for identifier in ("fast", "slow")]
    rules = {
        name: IndicatorRule(identifier, 2, {"a": 1}, output_column="custom", lookback_period=lookback)
        for name, identifier, lookback in (
            ("fast_one", "fast", 1), ("fast_three", "fast", 3),
            ("slow_one", "slow", 1), ("slow_two", "slow", 2),
        )
    }
    engine = IndicatorEngine(configs, [ConfluenceScoreConfig(
        id="native", rules=rules, group_thresholds={"a": 1},
    )],
                             [source("fast"), source("slow", "2h")])
    raw = {"fast": fast, "slow": slow}
    if prepared:
        engine.prepare(raw)
    expected = [
        (2, {"fast_one": False, "fast_three": True, "slow_one": True, "slow_two": True}),
        (3, {"fast_one": False, "fast_three": True, "slow_one": True, "slow_two": True}),
        (4, {"fast_one": False, "fast_three": False, "slow_one": False, "slow_two": True}),
        (5, {"fast_one": False, "fast_three": False, "slow_one": False, "slow_two": True}),
    ]
    for hours, matches in expected:
        result = engine.evaluate(raw, pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=hours))
        assert result.cards["native"]["matches"] == matches


@pytest.mark.parametrize("backend", ["pandas", "polars"])
@pytest.mark.parametrize("timeframe,start,end", [
    ("1M", "2024-02-01", "2024-03-01"),
    ("1Y", "2024-01-01", "2025-01-01"),
])
def test_callable_calendar_completion_and_nanosecond_timestamps(backend, timeframe, start, end):
    stamp = pd.Timestamp(start, tz="UTC") + pd.Timedelta(nanoseconds=123)
    raw = pd.DataFrame({"Close": [7.], "custom_field": [2.]}, index=[stamp])
    if backend == "polars":
        raw = pl.from_pandas(raw.rename_axis("Datetime").reset_index())
    calls = []

    def calculate(frame):
        calls.append(len(frame))
        if isinstance(frame, pl.DataFrame):
            assert frame.schema["Datetime"] == raw.schema["Datetime"]
            return frame.with_columns(pl.col("Close").alias("custom"))
        return frame.assign(custom=frame.Close)

    cfg = config(calculate=calculate, parameters={}, minimum_history=1)
    engine = IndicatorEngine([cfg], [], [source(timeframe=timeframe)]).prepare({"prices": raw})
    complete = pd.Timestamp(end, tz="UTC") + pd.Timedelta(nanoseconds=123)
    assert not engine.evaluate({}, complete - pd.Timedelta(nanoseconds=1)).ready["custom"]
    assert calls == []
    assert engine.evaluate({}, complete).values["custom"]["custom"] == 7
    assert calls == [1]


@pytest.mark.parametrize("backend", ["pandas", "polars"])
def test_callable_can_return_opposite_dataframe_backend(backend):
    def calculate(frame):
        output = custom(frame)
        if isinstance(output, pl.DataFrame):
            return output.to_pandas()
        return pl.from_pandas(output.rename_axis("Datetime").reset_index())

    engine = IndicatorEngine([config(calculate=calculate, parameters={})], [], [source()])
    result = engine.evaluate({"prices": prices(backend)}, pd.Timestamp("2024-01-01 02:00", tz="UTC"))
    assert result.values["custom"]["custom"] == 60


@pytest.mark.parametrize("prepared", [False, True])
def test_callable_mutations_rewinds_and_fresh_prepare(prepared):
    calls = []

    def calculate(frame):
        calls.append(len(frame))
        frame["custom"] = frame.Close.cumsum()
        frame["High"] = 999.
        return frame

    raw = prices()
    before = raw.copy(deep=True)
    cfg = config(calculate=calculate, parameters={})
    engine = IndicatorEngine([cfg], [], [source()])
    if prepared:
        engine.prepare({"prices": raw})
    now = pd.Timestamp("2024-01-01 04:00", tz="UTC")
    assert engine.evaluate({"prices": raw}, now).values["custom"]["custom"] == 10
    assert engine.evaluate({"prices": raw}, now).values["custom"]["custom"] == 10
    assert calls == [4, 4]
    assert_frame_equal(raw, before)
    changed = raw.copy(deep=True)
    changed.iloc[0, changed.columns.get_loc("custom_field")] = -100
    with pytest.raises(ValueError, match="changed overlapping"):
        engine.evaluate({"prices": changed}, now)
    with pytest.raises(ValueError, match="rewind"):
        engine.evaluate({}, now - pd.Timedelta(hours=1))
    engine.prepare({"prices": raw.iloc[3:]})
    reset = engine.evaluate({}, now + pd.Timedelta(hours=1))
    assert reset.values["custom"]["custom"] == 9
    assert calls == [4, 4, 2]


def test_callable_precompute_fresh_prepare_reinvokes_and_rejects_extensions():
    calls = []

    def calculate(frame):
        calls.append(len(frame))
        return custom(frame)

    raw = prices()
    engine = IndicatorEngine([
        config(calculate=calculate, parameters={}, execution="precompute"),
    ], [], [source()])
    engine.prepare({"prices": raw.iloc[:3]})
    engine.evaluate({}, pd.Timestamp("2024-01-01 03:00", tz="UTC"))
    with pytest.raises(ValueError, match="extends prepared history"):
        engine.evaluate({"prices": raw}, pd.Timestamp("2024-01-01 04:00", tz="UTC"))
    engine.prepare({"prices": raw})
    engine.evaluate({}, pd.Timestamp("2024-01-01 08:00", tz="UTC"))
    assert calls == [3, 8]
