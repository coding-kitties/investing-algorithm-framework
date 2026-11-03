import pickle

import pytest

from investing_algorithm_framework import (
    DataSource, OperationalException, PositionSize, ScalingRule, Schedule,
    StopLossRule, TakeProfitRule, TradingStrategy,
)


def scaling(**kwargs):
    return ScalingRule(max_entries=3, **kwargs)


def position(**kwargs):
    return PositionSize(percentage_of_portfolio=20, **kwargs)


def stop_loss(**kwargs):
    return StopLossRule(7, 100, **kwargs)


def take_profit(**kwargs):
    return TakeProfitRule(10, 100, **kwargs)


FACTORIES = [scaling, position, stop_loss, take_profit]


def strategy(**kwargs):
    return TradingStrategy(
        schedule=Schedule.every(1, "hour"),
        data_sources=[DataSource(
            symbol="BTC/EUR", market="BITVAVO",
            data_type="ohlcv", time_frame="1h",
        )],
        **kwargs,
    )


@pytest.mark.parametrize("factory", FACTORIES)
def test_symbols_are_normalized_copied_and_picklable(factory):
    symbols = ["btc", "ETH"]
    rule = factory(symbols=symbols)
    symbols.append("SOL")
    assert rule.symbols == ("BTC", "ETH")
    assert rule.symbol is None
    copied = pickle.loads(pickle.dumps(rule))
    assert copied.symbols == rule.symbols
    assert repr(copied) == repr(rule)
    assert "ETH" in repr(rule)
    assert factory(symbols=("BTC", "ETH")).symbols == rule.symbols


@pytest.mark.parametrize("factory", FACTORIES)
def test_legacy_symbol_is_supported(factory):
    rule = factory(symbol="BTC")
    assert rule.symbol == "BTC"
    assert rule.symbols == ("BTC",)


@pytest.mark.parametrize("factory", FACTORIES)
@pytest.mark.parametrize("symbols", [
    [], (), "BTC", {"BTC"}, {"BTC": True}, [None], [1], [""],
    [" BTC"], ["BTC "], ["BTC/EUR"], ["BTC", "btc"],
])
def test_invalid_symbols_raise(factory, symbols):
    with pytest.raises(ValueError, match="symbols must contain"):
        factory(symbols=symbols)


@pytest.mark.parametrize("factory", FACTORIES)
def test_selectors_are_mutually_exclusive(factory):
    with pytest.raises(ValueError, match="either symbol or symbols"):
        factory(symbol="BTC", symbols=["ETH"])


@pytest.mark.parametrize("factory,attribute,getter", [
    (scaling, "scaling_rules", "get_scaling_rule"),
    (position, "position_sizes", "get_position_size"),
])
@pytest.mark.parametrize("default_first", [False, True])
def test_explicit_symbols_override_defaults(
    factory, attribute, getter, default_first,
):
    default = factory()
    shared = factory(symbols=["BTC", "ETH"])
    rules = [default, shared] if default_first else [shared, default]
    instance = strategy(**{attribute: rules})
    resolve = getattr(instance, getter)
    assert resolve("BTC") is shared
    assert resolve("ETH") is shared
    assert resolve("SOL") is default


@pytest.mark.parametrize("factory,attribute,getter", [
    (stop_loss, "stop_losses", "get_stop_loss_rule"),
    (take_profit, "take_profits", "get_take_profit_rule"),
])
def test_shared_risk_rules_preserve_side_fallback(factory, attribute, getter):
    shared = factory(symbols=["BTC", "ETH"], mirror_on_exchange=True)
    short = factory(symbols=["BTC", "ETH"], side="short", trailing=True)
    instance = strategy(**{attribute: [short, shared]})
    resolve = getattr(instance, getter)
    for symbol in ("BTC", "ETH"):
        assert resolve(symbol) is shared
        assert resolve(symbol, "long") is shared
        assert resolve(symbol, "short") is short
        assert resolve(symbol).mirror_on_exchange
        assert resolve(symbol, "short").trailing
    assert resolve("SOL", "short") is None


def test_unlisted_symbols_do_not_inherit_shared_rules():
    instance = strategy(
        position_sizes=[position(symbols=["BTC", "ETH"])],
        scaling_rules=[scaling(symbols=["BTC", "ETH"])],
    )
    assert instance.get_scaling_rule("SOL") is None
    with pytest.raises(OperationalException, match="No position size"):
        instance.get_position_size("SOL")


def test_positional_constructors_remain_compatible():
    assert ScalingRule("BTC", 3, 40, 50, 90, 2, 20).symbol == "BTC"
    assert PositionSize("BTC", 20, None).symbol == "BTC"
    for rule_type in (StopLossRule, TakeProfitRule):
        rule = rule_type(7, 100, "BTC", True, "short", True)
        assert rule.symbol == "BTC"
        assert rule.trailing
        assert rule.side == "short"
        assert rule.mirror_on_exchange
