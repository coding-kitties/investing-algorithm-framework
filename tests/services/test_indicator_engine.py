"""Native indicator contracts: causality, scoring, and run-local parity."""
from dataclasses import FrozenInstanceError, replace
from copy import deepcopy
import json
from types import MappingProxyType
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import polars as pl
import pytest
from pandas.testing import assert_frame_equal

from investing_algorithm_framework import (
    ConfluenceScoreCard, ConfluenceScoreConfig, DataSource, IndicatorConfig,
    IndicatorEngine, IndicatorRule, Rule, Schedule, TradingStrategy,
    Requirement, Veto, condition, RunReport,
    SignalSide,
)
from investing_algorithm_framework.services.strategy_phases import (
    CollectSignalsPhase, DEFAULT_PHASES, EvaluateIndicatorsPhase, PhaseState,
)


def source(identifier="prices", symbol="BTC/EUR", timeframe="2h", warmup=100):
    return DataSource(
        identifier=identifier, symbol=symbol, data_type="ohlcv",
        time_frame=timeframe, warmup_window=warmup,
    )


def prices(n=90, timeframe="2h"):
    index = pd.date_range("2024-01-01", periods=n, freq=timeframe, tz="UTC")
    close = 100 + np.arange(n) * 0.2 + 3 * np.sin(np.arange(n) * 0.7)
    return pd.DataFrame({
        "Open": close - .1, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.ones(n),
    }, index=index)


def config(kind="ema", **kwargs):
    return IndicatorConfig(id=kwargs.pop("id", kind), indicator=kind,
                           data_source="prices", **kwargs)


def score(indicator_id="ema", **kwargs):
    return ConfluenceScoreConfig(
        rules={"entry": IndicatorRule(indicator_id, 1e6, {"primary": 2}, **kwargs)},
        group_thresholds={"primary": 2},
    )


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("rule_delay", [False, True])
@pytest.mark.parametrize("mode, expected", [
    ("continuous", [False, False, False, False, True, True, True, False]),
    ("recheck", [False, False, True, True, True, True, True, False]),
])
def test_initial_delay_counts_decisions_not_native_bars(prepared, rule_delay, mode, expected):
    raw = prices(8)
    raw["Close"] = [-2.5, -4, -2.5, -2.5, -2.5, -2.5, -2.5, -4]
    rule = IndicatorRule("ema", -2, {"primary": 2}, lower_bound=-3)
    declaration = (
        replace(score(), rules={"entry": replace(rule, initial_delay=2, initial_delay_mode=mode)})
        if rule_delay else replace(
            score(), initial_delay=2, initial_delay_mode=mode, rules={"entry": rule},
        )
    )
    engine = IndicatorEngine([config(period=1)], {"entry": declaration}, [source()])
    if prepared:
        engine.prepare({"prices": raw})
    decisions = raw.index + pd.Timedelta(hours=2)
    flags = []
    for stamp in decisions:
        payload = engine.evaluate({"prices": raw}, stamp).cards["entry"]
        flags.append(payload["passed"])
        assert engine.evaluate({"prices": raw}, stamp).cards["entry"] == payload
        assert payload["qualified"] == payload["passed"]
    assert flags == expected
    engine.prepare({"prices": raw})
    assert engine.card_signal_series(decisions)["entry"].tolist() == expected
    engine.prepare({"prices": raw})
    fast = pd.date_range(decisions[0], periods=4, freq="30min")
    assert engine.card_signal_series(fast)["entry"].tolist() == [False, False, True, True]
    assert [
        engine.evaluate({"prices": raw}, stamp).cards["entry"]["passed"]
        for stamp in fast
    ] == [False, False, True, True]


@pytest.mark.parametrize("prepared", [False, True])
def test_inclusive_bounds_use_one_observation_and_one_weight(prepared):
    raw = prices(9)
    raw["Close"] = [-3.1, -3, -2.5, -2, -1.9, np.nan, -4, -1, -2.5]
    rule = IndicatorRule("ema", -2, {"primary": 2}, lower_bound=-3)
    engine = IndicatorEngine(
        [config(period=1)], {"entry": replace(
            score(), rules={"entry": rule}, side=SignalSide.OPEN_LONG,
        )}, [source()],
    )
    if prepared:
        engine.prepare({"prices": raw})
    expected = [False, True, True, True, False, False, False, False, True]
    for stamp, passed in zip(raw.index + pd.Timedelta(hours=2), expected):
        evaluation = engine.evaluate({"prices": raw}, stamp)
        payload = evaluation.cards["entry"]
        assert payload["passed"] is passed
        assert payload["score"] == (2 if passed else 0)
    record = engine.confluence_snapshot(evaluation)[0]
    assert record["evaluations"][0]["lower_bound"] == -3
    assert ">= -3" in record["evaluations"][0]["condition"]
    inverse = IndicatorRule("ema", -3, {"primary": 2}, comparison="ge", upper_bound=-2)
    assert inverse.match(raw["Close"]).tolist() == expected


def test_delay_and_range_validation_and_serialization():
    import pickle

    for delay in (-1, True, 1.5, "2"):
        with pytest.raises(ValueError, match="initial_delay"):
            replace(score(), initial_delay=delay)
        with pytest.raises(ValueError, match="initial_delay"):
            score(initial_delay=delay)
    with pytest.raises(ValueError, match="initial_delay_mode"):
        replace(score(), initial_delay_mode="unknown")
    with pytest.raises(ValueError, match="initial_delay_mode"):
        score(initial_delay_mode="unknown")
    for bounds in (
        {"lower_bound": np.nan}, {"upper_bound": True},
        {"lower_bound": 3, "upper_bound": 2}, {"lower_bound": 2e6},
    ):
        with pytest.raises(ValueError):
            score(**bounds)
    rule = IndicatorRule(
        "ema", -2, {"primary": 2}, lower_bound=-3,
        initial_delay=2, initial_delay_mode="recheck",
    )
    declaration = replace(
        score(), rules={"entry": rule}, initial_delay=3, initial_delay_mode="recheck",
    )
    assert pickle.loads(pickle.dumps(declaration)) == declaration


@pytest.mark.parametrize("rule_delay", [False, True])
def test_delay_resets_on_skipped_cards_and_fresh_runs(rule_delay):
    raw = prices(4)
    declaration = score(initial_delay=1) if rule_delay else replace(score(), initial_delay=1)
    engine = IndicatorEngine([config(period=1)], {"entry": declaration}, [source()])
    engine.prepare({"prices": raw})
    stamps = raw.index + pd.Timedelta(hours=2)
    assert not engine.evaluate({"prices": raw}, stamps[0]).cards["entry"]["passed"]
    engine.evaluate({"prices": raw}, stamps[1], inactive_cards={"entry": "inactive"})
    assert not engine.evaluate({"prices": raw}, stamps[2]).cards["entry"]["passed"]
    assert engine.evaluate({"prices": raw}, stamps[3]).cards["entry"]["passed"]
    engine.prepare({"prices": raw})
    assert not engine.evaluate({"prices": raw}, stamps[0]).cards["entry"]["passed"]


@pytest.mark.parametrize("rule_delay", [False, True])
def test_delayed_exit_restarts_for_new_fill_and_trace_shows_pending_confirmation(rule_delay):
    raw = prices(6)
    declaration = (
        replace(score(initial_delay=2), side=SignalSide.CLOSE_LONG)
        if rule_delay else replace(score(), side=SignalSide.CLOSE_LONG, initial_delay=2)
    )
    engine = IndicatorEngine([config(period=1)], {"exit": declaration}, [source()])
    engine.prepare({"prices": raw})
    stamps = raw.index + pd.Timedelta(hours=2)
    first = engine.evaluate(
        {"prices": raw}, stamps[1], position_opened_at={"exit": stamps[0]},
    )
    record = engine.confluence_snapshot(first)[0]
    delayed = record["rule_delays"]["entry"] if rule_delay else record
    assert delayed["raw_matched" if rule_delay else "raw_passed"]
    assert delayed["delay_pending"] and not record["qualified"]
    entries = {item["name"]: item["value"] for item in record["decision_trace"]["entries"]}
    assert entries["entry.delay_elapsed" if rule_delay else "delay_elapsed"] == 0
    assert not engine.evaluate(
        {"prices": raw}, stamps[2], position_opened_at={"exit": stamps[0]},
    ).cards["exit"]["passed"]
    assert engine.evaluate(
        {"prices": raw}, stamps[3], position_opened_at={"exit": stamps[0]},
    ).cards["exit"]["passed"]
    assert not engine.evaluate(
        {"prices": raw}, stamps[4], position_opened_at={"exit": stamps[3]},
    ).cards["exit"]["passed"]
    with pytest.raises(ValueError, match="fill-driven"):
        engine.card_signal_series(stamps)


@pytest.mark.parametrize("prepared", [False, True])
def test_rule_delays_filter_weights_independently_before_group_scoring(prepared):
    raw = prices(6)
    raw["Close"] = [-2, -2, 2, -2, -2, -2]
    rules = {
        "delayed": IndicatorRule("ema", 0, {"primary": 1, "total": 1}, initial_delay=2),
        "support": IndicatorRule("ema", 0, {"secondary": 1, "total": 1}),
        "always": IndicatorRule("ema", 100, {"secondary": 1, "total": 1}),
    }
    declaration = ConfluenceScoreConfig(
        rules=rules, group_thresholds={"total": 2}, side=SignalSide.OPEN_LONG,
    )
    engine = IndicatorEngine([config(period=1)], {"entry": declaration}, [source()])
    if prepared:
        engine.prepare({"prices": raw})
    stamps = raw.index + pd.Timedelta(hours=2)
    payloads = [engine.evaluate({"prices": raw}, stamp).cards["entry"] for stamp in stamps]
    assert [payload["passed"] for payload in payloads] == [True, True, False, True, True, True]
    assert [payload["matches"]["delayed"] for payload in payloads] == [
        False, False, False, False, False, True,
    ]
    assert [next(group["score"] for group in payload["groups"] if group["name"] == "total")
            for payload in payloads] == [2, 2, 1, 2, 2, 3]
    engine.prepare({"prices": raw})
    assert engine.card_signal_series(stamps)["entry"].tolist() == [
        True, True, False, True, True, True,
    ]
    assert engine.evaluate({"prices": raw}, stamps[0]).cards["entry"] == payloads[0]

@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("rule_mode", ["continuous", "recheck"])
@pytest.mark.parametrize("card_mode", ["continuous", "recheck"])
def test_rule_and_card_delays_compose(prepared, rule_mode, card_mode):
    raw = prices(6)
    declaration = replace(
        score(initial_delay=1, initial_delay_mode=rule_mode),
        initial_delay=2, initial_delay_mode=card_mode, side=SignalSide.OPEN_LONG,
    )
    engine = IndicatorEngine([config(period=1)], {"entry": declaration}, [source()])
    if prepared:
        engine.prepare({"prices": raw})
    stamps = raw.index + pd.Timedelta(hours=2)
    payloads = [engine.evaluate({"prices": raw}, stamp).cards["entry"] for stamp in stamps]
    assert [payload["matches"]["entry"] for payload in payloads] == [
        False, True, True, True, True, True,
    ]
    assert [payload["raw_passed"] for payload in payloads] == [
        False, True, True, True, True, True,
    ]
    expected = [False, False, False, True, True, True]
    assert [payload["passed"] for payload in payloads] == expected
    engine.prepare({"prices": raw})
    assert engine.card_signal_series(stamps)["entry"].tolist() == expected
    evaluation = engine.evaluate({"prices": raw}, stamps[0])
    record = engine.confluence_snapshot(evaluation)[0]
    assert record["initial_delay"] == 2
    assert record["rule_delays"]["entry"]["initial_delay"] == 1
    assert record["evaluations"][0]["initial_delay"] == 1
    entries = {item["name"]: item["value"] for item in record["decision_trace"]["entries"]}
    assert entries["initial_delay"] == 2
    assert entries["entry.initial_delay"] == 1


def test_recheck_failed_deadline_rearms_and_bounds_match_same_lookback_bar():
    raw = prices(8)
    raw["Close"] = [-2.5, -4, -4, -2.5, -2.5, -2.5, -4, -1]
    rule = IndicatorRule("ema", -2, {"primary": 2}, lower_bound=-3)
    engine = IndicatorEngine([config(period=1)], {
        "entry": replace(
            score(), rules={"entry": rule}, initial_delay=2, initial_delay_mode="recheck",
        ),
        "lookback": replace(score(), rules={"entry": replace(rule, lookback_period=2)}),
    }, [source()])
    engine.prepare({"prices": raw})
    decisions = raw.index + pd.Timedelta(hours=2)
    assert engine.card_signal_series(decisions)["entry"].tolist() == [
        False, False, False, False, False, True, False, False,
    ]
    last = engine.evaluate({"prices": raw}, decisions[-1]).cards["lookback"]
    assert not last["passed"]


@pytest.mark.parametrize("prepared", [False, True])
def test_position_lookback_excludes_entry_bar_and_preserves_indicator_history(prepared):
    raw = prices(18)
    raw["Close"] = [101., 97., 97., 101.] + [97.] * 14
    declaration = ConfluenceScoreConfig(
        id="exit", side=SignalSide.CLOSE_LONG,
        rules={"recovered": IndicatorRule(
            "ema", 100, {"primary": 1}, comparison="ge",
            lookback_period=14, lookback_scope="position",
        )}, group_thresholds={"primary": 1},
    )
    engine = IndicatorEngine([config(period=1)], [declaration], [source()])
    if prepared:
        engine.prepare({"prices": raw})
    entry = raw.index[1] + pd.Timedelta(hours=2)
    for row, bound, expected in (
        (2, entry, False), (3, entry, True), (4, entry, True),
        (4, raw.index[3] + pd.Timedelta(hours=2), False),
        (17, entry, False),
    ):
        result = engine.evaluate(
            {"prices": raw}, raw.index[row] + pd.Timedelta(hours=2),
            position_opened_at={"exit": bound},
        )
        assert result.cards["exit"]["passed"] is expected
        assert result.ready["ema"]
        assert result.values["ema"]["value"] == raw["Close"].iloc[row]
        assert result.cards["exit"]["position_opened_at"] == bound.isoformat()
    captured = engine.confluence_snapshot(result)[0]
    rule = next(row for row in captured["evaluations"] if row["category"] == "score")
    assert rule["lookback_scope"] == "position"
    assert rule["position_opened_at"] == entry.isoformat()
    assert "after position entry" in rule["condition"]
    if prepared:
        with pytest.raises(ValueError, match="fill-driven"):
            engine.card_signal_series(raw.index)


def test_position_scope_validation_and_missing_fill_are_explicit():
    with pytest.raises(ValueError, match="lookback_scope"):
        IndicatorRule("ema", 0, {"primary": 1}, lookback_scope="unknown")
    rule = IndicatorRule("ema", 0, {"primary": 1}, lookback_scope="position")
    with pytest.raises(ValueError, match="close_long"):
        ConfluenceScoreConfig(id="entry", side=SignalSide.OPEN_LONG, rules={"r": rule})
    declaration = ConfluenceScoreConfig(
        id="exit", side=SignalSide.CLOSE_LONG, rules={"r": rule},
        group_thresholds={"primary": 1},
    )
    engine = IndicatorEngine([config(period=1)], [declaration], [source()])
    raw = prices(3)
    with pytest.raises(ValueError, match="actual entry fill"):
        engine.evaluate({"prices": raw}, raw.index[-1])


def test_position_scope_rescores_mixed_signed_rules_instead_of_masking_whole_card():
    raw = prices(4)
    raw["Close"] = [101., 97., 97., 97.]
    declaration = ConfluenceScoreConfig(
        id="exit", side=SignalSide.CLOSE_LONG,
        rules={
            "base": IndicatorRule("ema", 200, {"primary": 1}),
            "penalty": IndicatorRule(
                "ema", 100, {"primary": -1}, comparison="ge",
                lookback_period=14, lookback_scope="position",
            ),
        }, group_thresholds={"primary": 1},
    )
    engine = IndicatorEngine([config(period=1)], [declaration], [source()])
    engine.prepare({"prices": raw})
    entry, now = raw.index[1:3] + pd.Timedelta(hours=2)
    candidates = engine.card_signal_series(
        pd.DatetimeIndex([now]), position_scoped_candidates=True,
    )
    assert candidates["exit"].iloc[0]
    result = engine.evaluate(
        {"prices": raw}, now, position_opened_at={"exit": entry},
    )
    assert result.cards["exit"]["passed"] and result.cards["exit"]["score"] == 1
    assert engine.position_scoped_exit_signal(now, entry, side=SignalSide.CLOSE_LONG)
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.evaluate_card("exit", now, position_opened_at=entry.tz_localize(None))
    with pytest.raises(ValueError, match="future"):
        engine.evaluate_card("exit", now, position_opened_at=now + pd.Timedelta(hours=2))


def test_snapshot_captures_every_output_and_unavailable_warmup_values():
    engine = IndicatorEngine([
        config(period=2),
        config("macd", short_period=2, long_period=3, signal_period=2),
    ], {}, [source()])
    raw = prices(10)
    initial = engine.evaluate({}, raw.index[0])
    warmup = RunReport(indicators=engine.snapshot(initial)).to_dict()
    assert len(warmup["indicators"]) == 4
    assert all(record["value"] is None for record in warmup["indicators"])
    result = engine.evaluate(
        {"prices": raw}, raw.index[-1] + pd.Timedelta(hours=2),
    )
    snapshots = engine.snapshot(result)
    assert {record["name"] for record in snapshots} == {
        "ema.value", "macd.macd", "macd.signal", "macd.histogram",
    }
    assert all(record["symbol"] == "BTC" for record in snapshots)
    assert {record["name"]: record["value"] for record in snapshots} == {
        f"{name}.{column}": value
        for name, outputs in result.values.items()
        for column, value in outputs.items()
    }


def test_declarations_validation_freezing_binding_and_dedup():
    first = config(period=3)
    with pytest.raises(FrozenInstanceError):
        first.period = 5
    for kwargs in ({"period": 0}, {"period": True}, {"timeframe": "CURRENT"},
                   {"indicator": "future"}, {"scale": float("nan")}):
        with pytest.raises(ValueError):
            IndicatorConfig("bad", **({"indicator": "ema"} | kwargs))
    with pytest.raises(ValueError, match="comparison"):
        score(comparison="infer_from_name")
    with pytest.raises(ValueError, match="threshold"):
        IndicatorRule("ema", np.nan, {"a": 1})
    engine = IndicatorEngine(
        [first, config(id="alias", period=3, signal_period=2)], {}, [source()],
    )
    assert engine.calculation_count == 1
    assert engine.required_windows == {"prices": 3}
    assert isinstance(IndicatorEngine([first], {"a": score()}, [source()]).compiled_cards["a"], ConfluenceScoreCard)
    with pytest.raises(ValueError, match="exactly one"):
        IndicatorEngine([IndicatorConfig("ambiguous", "ema")], {}, [source(), source("other")])
    with pytest.raises(ValueError, match="exactly one"):
        IndicatorEngine([first], {}, [source(timeframe="1h")])
    with pytest.raises(ValueError, match="warmup_window"):
        IndicatorEngine([config(period=5)], {"a": score(lookback_period=4)}, [source(warmup=7)])
    with pytest.raises(ValueError, match="Unknown indicator"):
        IndicatorEngine([first], {"a": score("missing")}, [source()])
    with pytest.raises(ValueError, match="explicit output"):
        IndicatorEngine([config("macd")], {"a": score("macd")}, [source()])
    with pytest.raises(ValueError, match="Unknown macd output"):
        IndicatorEngine([config("macd")], {"a": score("macd", output="value")}, [source()])
    with pytest.raises(ValueError, match="Duplicate indicator"):
        IndicatorEngine([first, first], {}, [source()])
    with pytest.raises(ValueError, match="threshold exceeds"):
        ConfluenceScoreConfig({"rule": IndicatorRule("ema", 5, {"a": 1})}, group_thresholds={"a": 2})


def test_builtin_declarations_round_trip_and_copy_symbol_source_mappings():
    selection = {"BTC": "prices", "ETH/EUR": "eth"}
    declared = IndicatorConfig(
        "mapped", "z_score", period=3, timeframe="2h",
        data_source=selection, symbol="BTC/EUR", scale=2,
    )
    selection["BTC"] = "changed"
    assert declared.data_source["BTC"] == "prices"
    with pytest.raises(TypeError):
        declared.data_source["BTC"] = "changed"
    assert IndicatorConfig.from_dict(json.loads(json.dumps(declared.to_dict()))) == declared
    for kind in ("ema", "macd", "stochastic", "rsi", "wilders_rsi", "willr"):
        config = replace(declared, indicator=kind)
        assert IndicatorConfig.from_dict(config.to_dict()) == config
    explicit = replace(declared, data_source=source())
    assert explicit.to_dict()["data_source"] == "prices"


def test_strategy_constructor_preserves_indicator_and_card_mapping_values():
    declared = config()
    declared_card = score()
    strategy = TradingStrategy(
        schedule=Schedule.every(2, "hour"),
        indicator_configs=MappingProxyType({declared.id: declared}),
        confluence_cards=MappingProxyType({"entry": declared_card}),
    )
    assert strategy.indicator_configs == {declared.id: declared}
    assert strategy.confluence_cards == {"entry": declared_card}
    assert IndicatorEngine(
        strategy.indicator_configs, strategy.confluence_cards, [source()],
    ).calculation_count == 1


def test_prepared_cache_keeps_only_state_changes_and_scores_unique_states():
    raw = prices(2000)
    declared = IndicatorConfig(
        "value", calculate=lambda frame: frame,
        output_columns=["Close"], data_source="prices",
        execution="precompute",
    )
    declared_card = ConfluenceScoreConfig(
        rules={"match": IndicatorRule(
            "value", 100, {"primary": 1}, output_column="Close",
        )}, group_thresholds={"primary": 1},
    )
    engine = IndicatorEngine([declared], {"entry": declared_card}, [source()])
    raw["Close"] = 99.
    with patch.object(engine, "_score_card", wraps=engine._score_card) as score:
        engine.prepare({"prices": raw})
    assert score.call_count == 2  # Initial unavailable state and one ready state.
    assert len(engine._card_outputs["entry"][0]) == 1
    expected = pd.Series(True, index=raw.index)
    expected.iloc[0] = False  # The first candle has not completed yet.
    actual = engine.card_signal_series(raw.index)["entry"]
    pd.testing.assert_series_equal(actual, expected)

    raw.iloc[::2, raw.columns.get_loc("Close")] = 101.
    with patch.object(engine, "_score_card", wraps=engine._score_card) as score:
        engine.prepare({"prices": raw})
    assert score.call_count == 3  # Alternation does not score every candle.
    assert len(engine._card_outputs["entry"][0]) == len(raw)
    expected.iloc[1::2] = False
    expected.iloc[2::2] = True
    pd.testing.assert_series_equal(
        engine.card_signal_series(raw.index)["entry"], expected,
    )


@pytest.mark.parametrize("as_of_offset", [0, 20])
def test_prepared_payload_copies_detach_every_mutable_field(as_of_offset):
    raw = prices(20)
    engine = IndicatorEngine(
        [config(period=2)], {"entry": score(lookback_period=3)}, [source()],
    ).prepare({"prices": raw})
    as_of = raw.index[0] + pd.Timedelta(hours=as_of_offset)
    first = engine.evaluate({}, as_of)
    expected_cards = deepcopy(first.cards)
    expected_readiness = deepcopy(first.rule_readiness)
    payload = first.cards["entry"]
    payload["groups"][0]["score"] = -999
    payload["groups"].append({"unexpected": True})
    payload["evaluations"][0]["matched"] = "mutated"
    payload["evaluations"].clear()
    payload["matches"]["entry"] = "mutated"
    payload["lookback_ready"]["entry"] = "mutated"
    payload["ready"] = "mutated"
    first.rule_readiness["entry"]["entry"] = "mutated"
    second = engine.evaluate({}, as_of)
    assert second.cards == expected_cards
    assert second.rule_readiness == expected_readiness


def test_packed_states_preserve_wide_rules_readiness_gates_and_lookbacks():
    columns = [f"value_{i}" for i in range(32)]
    raw = prices(30)
    random = np.random.default_rng(42)
    for column in columns:
        raw[column] = random.integers(0, 2, size=len(raw)).astype(float)
    raw.loc[raw.index[4:7], columns[0]] = np.nan
    raw.loc[raw.index[12], columns[-1]] = np.nan
    declared = IndicatorConfig(
        "wide", calculate=lambda frame: frame, output_columns=columns,
        data_source="prices", execution="precompute",
    )
    declared_card = ConfluenceScoreConfig(
        rules={
            column: IndicatorRule(
                "wide", 0, {"primary": -1 if i % 4 == 0 else 1},
                output_column=column, lookback_period=3,
            ) for i, column in enumerate(columns)
        },
        group_thresholds={"primary": 2},
        override_triggers=Rule(columns[3]),
        requirements=(Requirement(
            "required", condition(columns[1], "eq", value=True),
        ),),
        vetoes=(Veto(
            "veto", condition(columns[2], "eq", value=True),
        ),),
    )
    prepared = IndicatorEngine(
        [declared], {"entry": declared_card}, [source()],
    ).prepare({"prices": raw})
    event = IndicatorEngine([declared], {"entry": declared_card}, [source()])
    for i, now in enumerate(raw.index):
        actual = prepared.evaluate({}, now)
        expected = event.evaluate({"prices": raw.iloc[:i + 1]}, now)
        assert actual.cards == expected.cards
        assert actual.rule_readiness == expected.rule_readiness
        assert actual.ready == expected.ready
        for column in columns:
            assert actual.values["wide"][column] == pytest.approx(
                expected.values["wide"][column], nan_ok=True,
            )


def test_symbol_source_mappings_select_exactly_one_matching_source():
    declared = IndicatorConfig(
        "mapped", "z_score", period=3, timeframe="2h",
        data_source={"BTC": "prices", "ETH/EUR": "eth"}, symbol="BTC/EUR",
    )
    sources = [source(), source("eth", symbol="ETH/EUR")]
    for symbol in ("BTC/EUR", "ETH/EUR"):
        configured = replace(declared, symbol=symbol)
        engine = IndicatorEngine([configured], {}, sources)
        identifier = "prices" if symbol == "BTC/EUR" else "eth"
        assert set(engine.required_windows) == {identifier}
        frame = prices(10)
        result = engine.evaluate({identifier: frame}, frame.index[-1] + pd.Timedelta(hours=2))
        assert result.ready["mapped"]
    with pytest.raises(ValueError, match="explicit symbol"):
        IndicatorEngine([replace(declared, symbol=None)], {}, sources)
    with pytest.raises(ValueError, match="no data source"):
        IndicatorEngine([replace(declared, symbol="DOGE/EUR")], {}, sources)
    with pytest.raises(ValueError, match="exactly one"):
        IndicatorEngine([replace(declared, data_source={"BTC": "eth"})], {}, sources)


@pytest.mark.parametrize("selection", [
    {}, {"btc": "prices"}, {"BTC": ""}, {"BTC": " padded "}, {" BTC": "prices"},
])
def test_invalid_symbol_source_mappings_are_rejected(selection):
    with pytest.raises(ValueError, match="data_source"):
        IndicatorConfig("bad", "ema", data_source=selection)


@pytest.mark.parametrize("kind", ["z_score", "willr", "rsi", "wilders_rsi", "ema", "macd", "stochastic"])
def test_indicator_values_against_independent_formulas(kind):
    frame = prices(15)
    cfg = config(kind, period=3, short_period=2, long_period=4, signal_period=2, k_slowing=2, d_period=2)
    engine = IndicatorEngine([cfg], {}, [source()])
    result = engine.evaluate({"prices": frame}, frame.index[-1] + pd.Timedelta(hours=2))
    close = frame.Close
    if kind == "z_score":
        expected = (close - close.rolling(3).mean()) / close.rolling(3).std(ddof=0)
    elif kind == "willr":
        high, low = frame.High.rolling(3).max(), frame.Low.rolling(3).min()
        expected = -100 * (high - close) / (high - low)
    elif kind == "rsi":
        delta = close.diff()
        gain, loss = delta.clip(lower=0).rolling(3).mean(), -delta.clip(upper=0).rolling(3).mean()
        expected = 100 * gain / (gain + loss)
    elif kind == "wilders_rsi":
        delta = close.diff().iloc[1:]
        gain = delta.iloc[:3].clip(lower=0).mean()
        loss = -delta.iloc[:3].clip(upper=0).mean()
        for change in delta.iloc[3:]:
            gain = (gain * 2 + max(change, 0)) / 3
            loss = (loss * 2 + max(-change, 0)) / 3
        expected = pd.Series([100 * gain / (gain + loss)])
    elif kind == "ema":
        expected = close.ewm(span=3, adjust=False, min_periods=3).mean()
    elif kind == "macd":
        macd = close.ewm(span=2, adjust=False, min_periods=2).mean() - close.ewm(span=4, adjust=False, min_periods=4).mean()
        signal = macd.ewm(span=2, adjust=False, min_periods=2).mean()
        assert result.values[kind] == pytest.approx({
            "macd": macd.iloc[-1], "signal": signal.iloc[-1],
            "histogram": (macd - signal).iloc[-1],
        })
        return
    else:
        high, low = frame.High.rolling(3).max(), frame.Low.rolling(3).min()
        k = (100 * (close - low) / (high - low)).rolling(2).mean()
        assert result.values[kind] == pytest.approx({"k": k.iloc[-1], "d": k.rolling(2).mean().iloc[-1]})
        return
    assert result.values[kind]["value"] == pytest.approx(expected.iloc[-1])
    assert result.ready[kind]


@pytest.mark.parametrize("prepared", [False, True])
def test_z_score_known_population_standard_deviation(prepared):
    frame = prices(3)
    frame["Close"] = [1., 2., 3.]
    engine = IndicatorEngine([config("z_score", period=3)], {}, [source()])
    if prepared:
        engine.prepare({"prices": frame})
    result = engine.evaluate(
        {"prices": frame}, frame.index[-1] + pd.Timedelta(hours=2),
    )
    assert result.values["z_score"]["value"] == pytest.approx(np.sqrt(1.5))


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("invalid", [np.nan, np.inf])
@pytest.mark.parametrize("kind,closes,expected", [
    (
        "ema", [1, 2, 3, 4, None, 10, 12, 14],
        {"value": [np.nan, np.nan, 2.25, 3.125, np.nan, np.nan, np.nan, 12.5]},
    ),
    (
        "wilders_rsi", [1, 3, 2, 4, 3, None, 10, 12, 11, 13, 12],
        {"value": [
            np.nan, np.nan, np.nan, 80, 800 / 13,
            np.nan, np.nan, np.nan, np.nan, 80, 800 / 13,
        ]},
    ),
    (
        "macd", [1, 2, 3, 4, None, 10, 12, 14, 16],
        {
            "macd": [np.nan, np.nan, 11 / 36, 85 / 216, np.nan,
                     np.nan, np.nan, 11 / 18, 85 / 108],
            "signal": [np.nan, np.nan, np.nan, 59 / 162, np.nan,
                       np.nan, np.nan, np.nan, 59 / 81],
            "histogram": [np.nan, np.nan, np.nan, 19 / 648, np.nan,
                          np.nan, np.nan, np.nan, 19 / 324],
        },
    ),
])
def test_recursive_initialization_min_periods_and_missing_reseed_known_values(
    prepared, invalid, kind, closes, expected,
):
    # Exact fractions independently calculated from the published recurrences.
    frame = prices(len(closes))
    frame["Close"] = [invalid if value is None else value for value in closes]
    engine = IndicatorEngine(
        [config(kind, period=3, short_period=2, long_period=3, signal_period=2)],
        {}, [source()],
    )
    if prepared:
        engine.prepare({"prices": frame})
    observed = {output: [] for output in expected}
    for i, timestamp in enumerate(frame.index):
        evaluation = engine.evaluate(
            {"prices": frame.iloc[max(0, i - 3):i + 1]},
            timestamp + pd.Timedelta(hours=2),
        )
        for output in observed:
            observed[output].append(evaluation.values[kind][output])
    for output in expected:
        np.testing.assert_allclose(
            observed[output], expected[output], equal_nan=True,
            rtol=1e-13, atol=1e-13,
        )


@pytest.mark.parametrize("kind", ["rsi", "wilders_rsi"])
def test_rsi_zero_gain_and_loss_is_neutral(kind):
    frame = prices(5)
    frame["Close"] = 10.
    engine = IndicatorEngine([config(kind, period=3)], {}, [source()])
    value = engine.evaluate(
        {"prices": frame}, frame.index[-1] + pd.Timedelta(hours=2),
    ).values[kind]["value"]
    assert value == 50


def test_actual_card_weights_max_sum_negative_evidence_and_override():
    configs = [config(period=1)]
    rules = {
        "a": IndicatorRule("ema", 0, {"trend": 2, "entry": 1}, comparison="ge"),
        "b": IndicatorRule("ema", 0, {"trend": 3, "entry": 2}, comparison="ge"),
        "penalty": IndicatorRule("ema", 0, {"entry": -1}, comparison="ge"),
    }
    card = ConfluenceScoreConfig(
        rules, group_aggregation={"trend": "max", "entry": "sum"},
        group_thresholds={"trend": 3, "entry": 2},
    )
    engine = IndicatorEngine(configs, {"entry": card}, [source()])
    frame = prices(1)
    result = engine.evaluate({"prices": frame}, frame.index[0] + pd.Timedelta(hours=2))
    payload = result.cards["entry"]
    assert payload["passed"]
    assert {group["name"]: group["score"] for group in payload["groups"]} == {"entry": 2, "trend": 3}
    trend = [evaluation for evaluation in payload["evaluations"] if evaluation["group"] == "trend"]
    assert [evaluation["points"] for evaluation in trend] == [0, 3]
    override = ConfluenceScoreConfig(
        rules, group_thresholds={}, override_triggers=Rule("a"),
    )
    overridden = IndicatorEngine(configs, {"override": override}, [source()])
    assert overridden.evaluate({"prices": frame}, frame.index[0] + pd.Timedelta(hours=2)).cards["override"]["passed"]


def test_native_lookback_partial_readiness_and_current_invalid_gate():
    frame = prices(5)
    frame["Close"] = [1, 10, 10, np.nan, 10]
    engine = IndicatorEngine(
        [config(period=1)], {
            "entry": ConfluenceScoreConfig({
                "oversold": IndicatorRule("ema", 2, {"a": 1}, lookback_period=3),
            }, group_thresholds={"a": 1}),
        }, [source()],
    )
    # Sub-native decision frequency must not consume extra lookback positions.
    for offset in (2, 2.25, 2.5, 4, 5.5, 6):
        result = engine.evaluate({"prices": frame}, frame.index[0] + pd.Timedelta(hours=offset))
        assert result.cards["entry"]["passed"]
    assert result.cards["entry"]["lookback_ready"]["oversold"]
    invalid = engine.evaluate({"prices": frame}, frame.index[0] + pd.Timedelta(hours=8))
    assert not invalid.cards["entry"]["passed"]
    assert not invalid.rule_readiness["entry"]["oversold"]
    after = engine.evaluate({"prices": frame}, frame.index[0] + pd.Timedelta(hours=10))
    assert not after.cards["entry"]["passed"]


@pytest.mark.parametrize("missing", [False, True])
def test_all_prefix_event_rolling_windows_equal_prepared_and_inputs_unchanged(missing):
    frame = prices(65)
    if missing:
        frame.loc[frame.index[18:20], "Close"] = np.nan
        frame.loc[frame.index[32], "High"] = np.nan
    before = frame.copy(deep=True)
    kinds = ("z_score", "willr", "rsi", "wilders_rsi", "ema", "macd", "stochastic")
    configs = [config(kind, period=4, short_period=3, long_period=6, signal_period=3) for kind in kinds]
    configs.append(config("ema", id="ema_alias", period=4))
    rules = {
        kind: IndicatorRule(kind, 50, {"a": 1}, lookback_period=3,
                            output="histogram" if kind == "macd" else "d" if kind == "stochastic" else None)
        for kind in kinds
    }
    cards = {"entry": ConfluenceScoreConfig(rules, group_thresholds={"a": 3})}
    prepared = IndicatorEngine(configs, cards, [source()]).prepare({"prices": frame})
    event = IndicatorEngine(configs, cards, [source()])
    with patch.object(prepared.compiled_cards["entry"].__class__, "evaluate",
                      wraps=prepared.compiled_cards["entry"].evaluate) as scorer:
        for i in range(len(frame)):
            window = frame.iloc[max(0, i - 9):i + 1]
            for fraction in (0, .5, 1):
                as_of = frame.index[i] + pd.Timedelta(hours=2 * fraction)
                actual = event.evaluate({"prices": window}, as_of)
                calls_before = scorer.call_count
                expected = prepared.evaluate({"prices": window}, as_of)
                assert scorer.call_count == calls_before
                for name in actual.values:
                    for output, value in actual.values[name].items():
                        target = expected.values[name][output]
                        assert value == pytest.approx(target, nan_ok=True)
                assert actual.ready == expected.ready
                assert actual.cards == expected.cards
                assert actual.rule_readiness == expected.rule_readiness
                for output, value in actual.values["ema"].items():
                    assert value == pytest.approx(actual.values["ema_alias"][output], nan_ok=True)
        # Only event evaluations score; prepared dispatches cached payloads.
        assert scorer.call_count == len(frame) * 3
    assert_frame_equal(before, frame)


@pytest.mark.parametrize("timeframe,start,end", [
    ("2h", "2024-01-01 00:00", "2024-01-01 02:00"),
    ("1M", "2024-01-01 00:00", "2024-02-01 00:00"),
    ("1Y", "2024-01-01 00:00", "2025-01-01 00:00"),
])
def test_completed_candle_alignment_calendar_units_and_polars(timeframe, start, end):
    frame = pd.DataFrame({"Datetime": [pd.Timestamp(start)], "Close": [42.]})
    raw = pl.from_pandas(frame)
    engine = IndicatorEngine(
        [config(period=1, timeframe=timeframe)], {"entry": score()},
        [source(timeframe=timeframe)],
    ).prepare({"prices": raw})
    end = pd.Timestamp(end, tz="UTC")
    before = engine.evaluate({}, end - pd.Timedelta(nanoseconds=1))
    assert np.isnan(before.values["ema"]["value"])
    assert not before.cards["entry"]["passed"]
    assert engine.evaluate({}, end).values["ema"]["value"] == 42
    assert raw.to_dict(as_series=False) == pl.from_pandas(frame).to_dict(as_series=False)
    empty = engine.prepare({"prices": frame.iloc[:0]}).evaluate({}, end)
    assert not empty.ready["ema"]
    assert not empty.cards["entry"]["passed"]


def test_isolation_failures_and_symbol_resolution():
    frame = prices(10)
    engine = IndicatorEngine([config(period=2)], {}, [source()])
    now = frame.index[-1] + pd.Timedelta(hours=2)
    engine.evaluate({"prices": frame}, now)
    changed = frame.copy()
    changed.iloc[-1, changed.columns.get_loc("Close")] += 1
    with pytest.raises(ValueError, match="changed overlapping"):
        engine.evaluate({"prices": changed}, now)
    with pytest.raises(ValueError, match="rewind"):
        engine.evaluate({}, now - pd.Timedelta(hours=2))
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.evaluate({}, datetime(2024, 1, 1))
    reset = engine.prepare({"prices": frame.iloc[:1]}).evaluate({}, now)
    assert not reset.ready["ema"]
    with pytest.raises(ValueError, match="extends prepared"):
        engine.evaluate({"prices": frame}, now)
    with pytest.raises(ValueError, match="Missing prepared"):
        engine.prepare({})
    with pytest.raises(ValueError, match="missing columns"):
        engine.prepare({"prices": frame.drop(columns="Close")})
    with pytest.raises(ValueError, match="unique and increasing"):
        engine.prepare({"prices": frame.iloc[::-1]})
    with pytest.raises(ValueError, match="unique and increasing"):
        engine.prepare({"prices": pd.concat([frame, frame])})
    a, b = source("a"), source("b", symbol="ETH/EUR")
    per_symbol = IndicatorEngine(
        [IndicatorConfig("eth", "ema", period=1, symbol="ETH/EUR")], {}, [a, b],
    )
    result = per_symbol.evaluate({"a": frame * 10, "b": frame}, now)
    assert result.values["eth"]["value"] == frame.Close.iloc[-1]


def test_phase_opt_in_injection_engine_override_and_instance_isolation():
    class Strategy(TradingStrategy):
        schedule = Schedule.every(2, "hour")
        indicator_configs = [config(period=2)]
        confluence_cards = {"entry": score()}
        data_sources = [source()]

    first, second = Strategy(), Strategy()
    assert first.confluence_cards is not second.confluence_cards
    assert DEFAULT_PHASES.index(EvaluateIndicatorsPhase) < DEFAULT_PHASES.index(CollectSignalsPhase)
    data = {"prices": prices(3)}
    state = PhaseState(first, SimpleNamespace(), data, data["prices"].index[-1] + pd.Timedelta(hours=2))
    EvaluateIndicatorsPhase().run(state)
    assert state.data["indicators"].cards["entry"]["passed"]
    assert not hasattr(second, "_indicator_engine")
    custom = Mock()
    second._indicator_engine = custom
    replacement = PhaseState(second, SimpleNamespace(), {}, state.current_datetime)
    EvaluateIndicatorsPhase().run(replacement)
    assert replacement.data["indicators"] is custom.evaluate.return_value
    plain = PhaseState(TradingStrategy(schedule=Schedule.every(2, "hour")), SimpleNamespace(), {}, state.current_datetime)
    EvaluateIndicatorsPhase().run(plain)
    assert plain.data == {}


def test_partial_window_readiness_nonfinite_ne_and_empty_inputs():
    frame = prices(3)
    frame["Close"] = [2, np.nan, 4]
    cards = {
        "entry": ConfluenceScoreConfig({
            "different": IndicatorRule(
                "ema", 1, {"a": 1}, lookback_period=3, comparison="ne",
            ),
        }, group_thresholds={"a": 1}),
    }
    event = IndicatorEngine([config(period=1)], cards, [source()])
    empty = event.evaluate({"prices": pd.DataFrame()}, frame.index[0])
    assert not empty.ready["ema"]
    partial = event.evaluate({"prices": frame.iloc[:1]}, frame.index[1])
    assert partial.cards["entry"]["passed"]
    assert partial.rule_readiness["entry"]["different"]
    assert not partial.cards["entry"]["lookback_ready"]["different"]
    missing = event.evaluate({"prices": frame}, frame.index[2])
    assert not missing.cards["entry"]["passed"]
    assert not missing.cards["entry"]["matches"]["different"]
    # Omitting a source preserves the last known completed (invalid) row.
    assert not event.evaluate({}, frame.index[2] + pd.Timedelta(minutes=10)).ready["ema"]
    recovered = event.evaluate({"prices": frame}, frame.index[-1] + pd.Timedelta(hours=2))
    assert recovered.cards["entry"]["passed"]
    assert not recovered.cards["entry"]["lookback_ready"]["different"]


def test_multitimeframe_alignment_no_symbol_leakage_scale_and_card_cache_isolation():
    slow = prices(12, "4h")
    fast = prices(24)
    configurations = [
        IndicatorConfig("btc", "ema", period=2, timeframe="2h", data_source="btc", scale=2),
        IndicatorConfig("eth", "ema", period=2, timeframe="4h", data_source="eth"),
    ]
    sources = [source("btc"), source("eth", symbol="ETH/EUR", timeframe="4h")]
    cards = {"both": ConfluenceScoreConfig({
        "btc": IndicatorRule("btc", 0, {"a": 1}, comparison="ge", lookback_period=3),
        "eth": IndicatorRule("eth", 0, {"a": 1}, comparison="ge", lookback_period=2),
    }, group_thresholds={"a": 2})}
    event = IndicatorEngine(configurations, cards, sources)
    prepared = IndicatorEngine(configurations, cards, sources).prepare({"btc": fast, "eth": slow})
    for as_of in pd.date_range(fast.index[0], fast.index[-1] + pd.Timedelta(hours=2), freq="1h"):
        data = {
            "btc": fast.loc[fast.index <= as_of].iloc[-5:],
            "eth": slow.loc[slow.index <= as_of].iloc[-5:],
        }
        actual, expected = event.evaluate(data, as_of), prepared.evaluate(data, as_of)
        for name in actual.values:
            assert actual.values[name]["value"] == pytest.approx(expected.values[name]["value"], nan_ok=True)
        assert actual.cards == expected.cards
    assert actual.values["btc"]["value"] == pytest.approx(fast.Close.ewm(span=2, adjust=False).mean().iloc[-1] * 2)
    expected.cards["both"]["matches"]["btc"] = False
    repeated = prepared.evaluate({}, as_of)
    assert repeated.cards["both"]["matches"]["btc"]


def test_requirements_vetoes_and_native_output_rule_readiness():
    frame = prices(6)
    rule = IndicatorRule("macd", -1e6, {"a": 1}, output="macd", comparison="ge")
    cards = {
        "allow": ConfluenceScoreConfig(
            {"positive": rule}, group_thresholds={"a": 1},
            requirements=(Requirement("must_match", condition("positive", "eq", value=True)),),
        ),
        "veto": ConfluenceScoreConfig(
            {"positive": rule}, group_thresholds={"a": 1},
            vetoes=(Veto("never", condition("positive", "eq", value=True)),),
        ),
    }
    engine = IndicatorEngine(
        [config("macd", short_period=2, long_period=3, signal_period=4)],
        cards, [source()],
    ).prepare({"prices": frame})
    early = engine.evaluate({}, frame.index[2] + pd.Timedelta(hours=2))
    assert not early.ready["macd"]  # Signal/histogram need more native bars.
    assert early.rule_readiness["allow"]["positive"]
    assert early.cards["allow"]["passed"]
    assert not early.cards["veto"]["passed"]
    with pytest.raises(ValueError, match="named indicator-rule"):
        ConfluenceScoreConfig(
            {"positive": rule}, group_thresholds={"a": 1},
            requirements=(Requirement("bad", condition("missing", "eq", value=True)),),
        )


def test_dedup_computes_once_and_fresh_prepare_discards_recursive_origin():
    from investing_algorithm_framework.services import indicator_engine as module
    frame = prices(30)
    configs = [config(period=3), config(id="alias", period=3)]
    engine = IndicatorEngine(configs, {"a": score(), "b": score(lookback_period=4)}, [source()])
    with patch.object(module, "compute_indicator", wraps=module.compute_indicator) as compute:
        engine.prepare({"prices": frame})
        assert compute.call_count == 1
        engine.evaluate({}, frame.index[-1] + pd.Timedelta(hours=2))
        assert compute.call_count == 1
    old = engine.evaluate({}, frame.index[-1] + pd.Timedelta(hours=2))
    modified = frame.iloc[-10:].copy()
    modified["Close"] += 500
    fresh = engine.prepare({"prices": modified}).evaluate({}, frame.index[-1] + pd.Timedelta(hours=2))
    independent = IndicatorEngine(configs, {"a": score(), "b": score(lookback_period=4)}, [source()]).evaluate(
        {"prices": modified}, frame.index[-1] + pd.Timedelta(hours=2),
    )
    assert fresh.values == independent.values
    assert fresh.values != old.values


def test_inserted_old_observation_is_rejected_without_mutating_inputs():
    frame = prices(5)
    engine = IndicatorEngine([config(period=1)], {}, [source()])
    now = frame.index[-1] + pd.Timedelta(hours=2)
    engine.evaluate({"prices": frame.iloc[[0, 2, 3, 4]]}, now)
    before = frame.copy()
    with pytest.raises(ValueError, match="inserts historical"):
        engine.evaluate({"prices": frame}, now)
    assert_frame_equal(frame, before)
