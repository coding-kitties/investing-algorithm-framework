from importlib.util import find_spec
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from investing_algorithm_framework import (
    PortfolioConfiguration, PositionSize, ScalingRule, SignalSeries,
    SignalSide, StopLossRule, TakeProfitRule, TradingCost,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_native import native_events
from scripts.bench_vector_snapshot_events import (
    CyclingStrategy, result_digest, workload,
)


class SharedRuleStrategy(CyclingStrategy):
    def generate_signal_series(self, data):
        for symbol in self.symbols:
            index = data[f"{symbol}/EUR"].index
            for side, offset in (
                (SignalSide.OPEN_LONG, 0), (SignalSide.SCALE_IN, 2),
                (SignalSide.CLOSE_LONG, 4),
            ):
                yield SignalSeries(
                    symbol, side,
                    pd.Series([i == offset for i in range(len(index))],
                              index=index),
                )


def run(grouped, *, backend="python", hedge=False, scaling=False,
        risk_type=None, dynamic=False):
    service, arguments = workload(8, 3)
    symbols = ["ASSET0", "ASSET1"]
    instance = SharedRuleStrategy(symbols + ["ASSET2"])

    def declarations(rule_type, **kwargs):
        if grouped:
            return [rule_type(symbols=symbols, **kwargs)]
        return [rule_type(symbol=symbol, **kwargs) for symbol in symbols]

    instance.position_sizes = declarations(
        PositionSize, percentage_of_portfolio=10,
    ) + [PositionSize(percentage_of_portfolio=5)]
    if scaling:
        instance.scaling_rules = declarations(
            ScalingRule, max_entries=2, initial_entry_percentage=20,
            scale_in_percentage=40,
        )
    if risk_type:
        rules = declarations(
            risk_type, percentage_threshold=1, sell_percentage=100,
        )
        if risk_type is StopLossRule:
            instance.stop_losses = rules
        else:
            instance.take_profits = rules
    frames = service.data_provider_service.get_vectorized_backtest_data()
    prices = ([100.] * 8 if risk_type is None else
              [100.] + [98. if risk_type is StopLossRule else 102.] * 7)
    for frame in frames.values():
        for column in ("Open", "High", "Low", "Close"):
            frame[column] = prices
    arguments["strategy"] = instance
    arguments["portfolio_configuration"] = PortfolioConfiguration(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        position_mode="hedge" if hedge else "netting",
    )
    arguments["execution_backend"] = backend
    arguments["dynamic_position_sizing"] = dynamic
    return service.run(**arguments)


@pytest.mark.parametrize("hedge", [False, True])
@pytest.mark.parametrize("dynamic", [False, True])
@pytest.mark.parametrize("scaling", [False, True])
def test_shared_sizing_and_scaling_match_individual_rules(
    hedge, dynamic, scaling,
):
    kwargs = dict(hedge=hedge, dynamic=dynamic, scaling=scaling)
    expected = run(False, **kwargs)
    actual = run(True, **kwargs)
    assert result_digest(actual) == result_digest(expected)
    assert {trade.target_symbol for trade in actual.trades} == {
        "ASSET0", "ASSET1", "ASSET2",
    }
    if scaling:
        for symbol in ("ASSET0", "ASSET1"):
            entries = [trade for trade in actual.trades
                       if trade.target_symbol == symbol]
            assert len(entries) == 2
            assert pd.Timestamp(entries[1].opened_at).hour == 2


@pytest.mark.parametrize("risk_type", [StopLossRule, TakeProfitRule])
@pytest.mark.parametrize("backend,hedge", [
    ("python", False), ("python", True), ("rust", False),
])
def test_shared_risk_rules_match_individual_rules(risk_type, backend, hedge):
    if backend == "rust":
        if find_spec("iaf_confluence_native") is None:
            pytest.skip("Native extension is not installed")
        import iaf_confluence_native as native
        if getattr(native, "NETTING_SEMANTICS_VERSION", None) != (
            "netting-accounting-v6"
        ):
            pytest.skip("Native extension semantics are incompatible")
    kwargs = dict(backend=backend, hedge=hedge, risk_type=risk_type)
    actual = run(True, **kwargs)
    assert result_digest(actual) == result_digest(run(False, **kwargs))
    for symbol, hour in (("ASSET0", 1), ("ASSET1", 1), ("ASSET2", 4)):
        trade = next(trade for trade in actual.trades
                     if trade.target_symbol == symbol)
        assert pd.Timestamp(trade.closed_at).hour == hour


def test_native_risk_inputs_only_include_selected_symbols():
    symbols = ["BTC", "ETH", "SOL"]
    instance = SimpleNamespace(
        stop_losses=[StopLossRule(7, 100, symbols=["BTC", "ETH"])],
        take_profits=[TakeProfitRule(15, 100, symbols=["BTC", "ETH"])],
    )
    data = {
        symbol: {
            "trading_cost": TradingCost(symbol=symbol),
            "initial_capital_for_trade": 1000.,
            "pos_size_obj": PositionSize(
                symbols=["BTC", "ETH"], percentage_of_portfolio=10,
            ),
            "close": np.full(2, 100., dtype=np.float64),
            **{name: np.zeros(2, dtype=np.bool_) for name in (
                "buy_signal", "sell_signal", "short_signal", "cover_signal",
                "scale_in_signal", "scale_out_signal",
            )},
        } for symbol in symbols
    }
    native = SimpleNamespace(
        NETTING_SEMANTICS_VERSION="netting-accounting-v6",
        run_netting=Mock(return_value="native-result"),
    )
    with patch.dict(sys.modules, iaf_confluence_native=native):
        assert native_events(
            data, 2, 10000., instance, dynamic_position_sizing=False,
            hedge_mode=False, deposit_events=[],
        ) == "native-result"
    cooldowns, risks = native.run_netting.call_args.args[-1]
    assert cooldowns == []
    assert risks == [
        [(True, 15.), (False, 7.)],
        [(True, 15.), (False, 7.)],
        [],
    ]
