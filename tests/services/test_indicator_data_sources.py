from dataclasses import replace
import json
import pickle

import pandas as pd
import pytest

from investing_algorithm_framework import (
    DataSource, IndicatorConfig, IndicatorEngine,
)


def source(identifier, symbol="BTC/EUR", timeframe="1h"):
    return DataSource(
        identifier=identifier, symbol=symbol,
        data_type="ohlcv", time_frame=timeframe,
    )


def calculate(frame):
    return frame.assign(custom=frame["Close"] * 2)


def test_source_identifiers_and_objects_are_copied_and_serializable():
    selection = [source("btc"), "eth"]
    declared = IndicatorConfig(
        "ema", "ema", period=2, timeframe="1h", data_sources=selection,
    )
    selection.append("sol")
    assert declared.data_sources == ("btc", "eth")
    assert declared.data_source is None
    assert declared.source_identifiers == ("btc", "eth")
    definition = json.loads(json.dumps(declared.to_dict()))
    assert definition["data_sources"] == ["btc", "eth"]
    assert IndicatorConfig.from_dict(definition) == declared
    assert pickle.loads(pickle.dumps(declared)) == declared
    assert replace(declared, period=3).data_sources == ("btc", "eth")


def test_callable_plural_sources_remain_picklable_but_not_json_exportable():
    declared = IndicatorConfig(
        "custom", calculate=calculate, output_columns=["custom"],
        data_sources=["btc", "eth"],
    )
    copied = pickle.loads(pickle.dumps(declared))
    assert copied == declared
    assert copied.calculate is calculate
    with pytest.raises(TypeError, match="Callable indicators"):
        copied.to_dict()


@pytest.mark.parametrize("selection", [
    [], (), "btc", {"BTC": "btc"}, [None], [1], [""], [" btc"],
    ["btc "], ["btc", "btc"], [source("btc"), "btc"],
])
def test_invalid_plural_sources_raise(selection):
    with pytest.raises(ValueError, match="data_sources"):
        IndicatorConfig("ema", "ema", data_sources=selection)


@pytest.mark.parametrize("singular", [
    "btc", source("btc"), {"BTC": "btc"},
])
def test_singular_and_plural_sources_are_mutually_exclusive(singular):
    with pytest.raises(ValueError, match="either data_source or data_sources"):
        IndicatorConfig(
            "ema", "ema", data_source=singular, data_sources=["btc"],
        )


def test_legacy_serialization_and_positional_arguments_are_unchanged():
    declared = IndicatorConfig("ema", "ema", 2, "1h", "btc")
    assert declared.data_source == "btc"
    assert declared.data_sources is None
    assert "data_sources" not in declared.to_dict()
    assert IndicatorConfig.from_dict(declared.to_dict()) == declared


def test_direct_engine_resolves_only_selected_symbol_and_timeframe():
    sources = [
        source("btc"), source("eth", "ETH/EUR"), source("other"),
        source("btc_2h", timeframe="2h"),
    ]
    declared = IndicatorConfig(
        "ema", "ema", period=2, timeframe="1h", symbol="BTC/EUR",
        data_sources=["btc", "eth", "btc_2h"],
    )
    engine = IndicatorEngine([declared], {}, sources)
    assert engine.required_windows == {"btc": 2}
    raw = pd.DataFrame(
        {"Close": [1., 2., 3., 4.]},
        index=pd.date_range("2025-01-01", periods=4, freq="h", tz="UTC"),
    )
    result = engine.prepare({"btc": raw}).evaluate(
        {}, raw.index[-1] + pd.Timedelta(hours=1),
    )
    assert result.values["ema"]["value"] == pytest.approx(
        raw.Close.ewm(span=2, adjust=False).mean().iloc[-1],
    )


def test_ambiguous_sources_are_not_silently_selected():
    declared = IndicatorConfig(
        "ema", "ema", timeframe="1h", data_sources=["btc", "eth"],
    )
    with pytest.raises(ValueError, match="exactly one"):
        IndicatorEngine(
            [declared], {}, [source("btc"), source("eth", "ETH/EUR")],
        )
    with pytest.raises(ValueError, match="exactly one"):
        IndicatorEngine(
            [replace(declared, symbol="BTC/EUR")],
            {}, [source("btc"), source("eth")],
        )


def test_unknown_selected_source_is_reported_even_when_another_matches():
    declared = IndicatorConfig(
        "ema", "ema", timeframe="1h", symbol="BTC/EUR",
        data_sources=["btc", "missing"],
    )
    with pytest.raises(ValueError, match="Unknown data source: missing"):
        IndicatorEngine([declared], {}, [source("btc")])
