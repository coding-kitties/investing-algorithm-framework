from dataclasses import FrozenInstanceError, replace
import pickle
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from investing_algorithm_framework import (
    BacktestDateRange, BacktestEngine, BacktestRunConfiguration, BacktestWindow,
    CSVOHLCVDataProvider,
    ConfluenceScoreCard, ConfluenceScoringStrategy, ConfluenceScoreConfig, CooldownRule, DataSource,
    ExposureRule, IndicatorConfig, IndicatorRule, PortfolioConfiguration,
    PositionSize, RESOURCE_DIRECTORY, ScalingRule, Schedule, SignalSide, StopLossRule, Study,
    TradingCost, TradingStrategy, Universe, create_app,
)
from investing_algorithm_framework.domain import INDEX_DATETIME
from investing_algorithm_framework.infrastructure.services.backtesting.event_backtest_service import (
    EventBacktestService,
)
from investing_algorithm_framework.services.executors import Executor
from investing_algorithm_framework.services.strategy_phases import (
    ApplyRiskBudgetPhase, CollectSignalsPhase, EmitOrdersPhase,
    EvaluateIndicatorsPhase, RecordCooldownPhase, ResolveConflictsPhase,
    SizePositionsPhase,
)
from scripts.bench_vector_snapshot_events import workload


def calculate(frame):
    return frame.assign(zscore=frame["score"])


def source(symbol="ASSET0", **kwargs):
    return DataSource(
        identifier=f"{symbol}/EUR", symbol=f"{symbol}/EUR",
        market="BITVAVO", data_type="ohlcv", time_frame="1h",
        warmup_window=40, pandas=True, **kwargs,
    )


def config(**kwargs):
    return IndicatorConfig(**({
        "id": "zscore", "calculate": calculate, "output_columns": ["zscore"],
        "execution": "precompute",
    } | kwargs))


def card(name, side, threshold=-2, stage=None, **kwargs):
    return ConfluenceScoreConfig(
        id=name, side=side, scale_in_stage=stage,
        rules={"oversold": IndicatorRule(
            "zscore", threshold, {"primary": 1},
            output_column="zscore", lookback_period=1,
        )}, group_thresholds={"primary": 1}, **kwargs,
    )


def strategy(**kwargs):
    return ConfluenceScoringStrategy(**({
        "schedule": Schedule.every(1, "hour"),
        "data_sources": [source()],
        "indicator_configs": [config()],
        "confluence_cards": [
            card("entry", SignalSide.OPEN_LONG),
            card("first", SignalSide.SCALE_IN, -2.2, 0),
            card("second", SignalSide.SCALE_IN, -2.4, 1),
        ],
        "position_sizes": [PositionSize(percentage_of_portfolio=40)],
        "scaling_rules": [ScalingRule(
            max_entries=3, initial_entry_percentage=20,
            scale_in_percentage=[40, 40], cooldown_in_bars=2,
        )],
    } | kwargs))


def frame(scores):
    index = pd.date_range("2025-01-01", periods=len(scores), freq="h", tz="UTC")
    return pd.DataFrame({
        "Open": 100., "High": 100., "Low": 100., "Close": 100.,
        "Volume": 1000., "score": scores,
    }, index=index)


def position_exit_card(scope="position", side=SignalSide.CLOSE_LONG):
    return ConfluenceScoreConfig(
        id="exit", side=side,
        rules={"recovered": IndicatorRule(
            "zscore", 0, {"primary": 1}, output_column="zscore",
            comparison="ge", lookback_period=14, lookback_scope=scope,
        )}, group_thresholds={"primary": 1},
    )


@pytest.mark.parametrize("mode, entry_row", [("continuous", 45), ("recheck", 43)])
@pytest.mark.parametrize("engine", [BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR])
@pytest.mark.parametrize("minutes", [60, 120])
@pytest.mark.parametrize("rule_delay", [False, True])
def test_real_backtests_confirm_delayed_bounded_entry(tmp_path, mode, entry_row, engine, minutes, rule_delay):
    scores = [1.] * 39 + [-2.5] * 21
    scores[40] = -4.
    if minutes == 120:
        scores[41] = -4.
    raw = frame(scores)
    app = create_app(
        name="delayed-range", config={RESOURCE_DIRECTORY: str(tmp_path)},
    )
    app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=10000)
    csv = tmp_path / "prices.csv"
    raw.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
    app.add_data_provider(CSVOHLCVDataProvider(
        storage_path=str(csv), symbol="ASSET0/EUR", time_frame="1h",
        market="BITVAVO", warmup_window=40,
    ), priority=1)
    window = BacktestDateRange(raw.index[40].to_pydatetime(), raw.index[56].to_pydatetime())
    entry = replace(
        card("entry", SignalSide.OPEN_LONG, initial_delay=0 if rule_delay else 3, initial_delay_mode=mode),
        rules={"oversold": IndicatorRule(
            "zscore", -2, {"primary": 1}, output_column="zscore", lower_bound=-3,
            initial_delay=3 if rule_delay else 0, initial_delay_mode=mode,
        )},
    )
    backtests = app.run_backtest(
        strategy=strategy(
            algorithm_id="delayed-range", symbols=["ASSET0"],
            confluence_cards=[entry], scaling_rules=[],
            schedule=Schedule.every(minutes, "minute"),
        ),
        study=Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=window)], engines=[engine],
        ),
        run_configuration=BacktestRunConfiguration(
            capture_run_reports=engine is BacktestEngine.EVENT_DRIVEN,
            n_workers=0, show_progress=False, continue_on_error=False,
        ),
    )
    run = next(backtests.iter_backtests()).get_backtest_run(window)
    trades = run.get_trades()
    assert len(trades) == 1
    expected = (
        raw.index[entry_row] if minutes == 60 else
        raw.index[50 if mode == "continuous" else 46]
    )
    if engine is BacktestEngine.EVENT_DRIVEN:
        assert pd.Timestamp(trades[0].orders[0].created_at) == expected
        expected += pd.Timedelta(minutes=minutes)
    assert pd.Timestamp(trades[0].opened_at) == expected


@pytest.mark.parametrize("mode, exit_row", [("continuous", 48), ("recheck", 46)])
@pytest.mark.parametrize("scope", ["market", "position"])
@pytest.mark.parametrize("engine", [BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR])
@pytest.mark.parametrize("rule_delay", [False, True])
def test_real_backtests_delay_exit_confirmation(tmp_path, mode, exit_row, scope, engine, rule_delay):
    scores = [1.] * 39 + [-3.] * 21
    scores[43], scores[45], scores[46], scores[47] = 1., 1., 1., 1.
    raw = frame(scores)
    app = create_app(name="delayed-exit", config={RESOURCE_DIRECTORY: str(tmp_path)})
    app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=10000)
    csv = tmp_path / "prices.csv"
    raw.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
    app.add_data_provider(CSVOHLCVDataProvider(
        storage_path=str(csv), symbol="ASSET0/EUR", time_frame="1h",
        market="BITVAVO", warmup_window=40,
    ), priority=1)
    window = BacktestDateRange(raw.index[40].to_pydatetime(), raw.index[50].to_pydatetime())
    exit_card = replace(
        position_exit_card(scope), initial_delay=0 if rule_delay else 2, initial_delay_mode=mode,
        rules={"recovered": IndicatorRule(
            "zscore", 0, {"primary": 1}, comparison="ge", output_column="zscore",
            lookback_scope=scope,
            initial_delay=2 if rule_delay else 0, initial_delay_mode=mode,
        )},
    )
    backtests = app.run_backtest(
        strategy=strategy(
            algorithm_id="delayed-exit", symbols=["ASSET0"],
            confluence_cards=[card("entry", SignalSide.OPEN_LONG), exit_card],
            scaling_rules=[],
        ),
        study=Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=window)], engines=[engine],
        ),
        run_configuration=BacktestRunConfiguration(
            capture_run_reports=engine is BacktestEngine.EVENT_DRIVEN,
            n_workers=0, show_progress=False, continue_on_error=False,
        ),
    )
    run = next(backtests.iter_backtests()).get_backtest_run(window)
    closed = [trade for trade in run.get_trades() if trade.closed_at is not None]
    assert closed
    fill_delay = 1 if engine is BacktestEngine.EVENT_DRIVEN else 0
    assert pd.Timestamp(closed[0].closed_at) == raw.index[exit_row + fill_delay]


@pytest.mark.parametrize("engine", [BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR])
@pytest.mark.parametrize("rule_mode", ["continuous", "recheck"])
@pytest.mark.parametrize("card_mode", ["continuous", "recheck"])
def test_real_backtests_compose_rule_and_card_delays(tmp_path, engine, rule_mode, card_mode):
    raw = frame([1.] * 39 + [-3.] * 21)
    app = create_app(name="combined-delays", config={RESOURCE_DIRECTORY: str(tmp_path)})
    app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=10000)
    csv = tmp_path / "prices.csv"
    raw.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
    app.add_data_provider(CSVOHLCVDataProvider(
        storage_path=str(csv), symbol="ASSET0/EUR", time_frame="1h",
        market="BITVAVO", warmup_window=40,
    ), priority=1)
    window = BacktestDateRange(raw.index[40].to_pydatetime(), raw.index[50].to_pydatetime())
    entry = card(
        "entry", SignalSide.OPEN_LONG, initial_delay=2, initial_delay_mode=card_mode,
    )
    entry = replace(entry, rules={
        "oversold": replace(
            entry.rules["oversold"], initial_delay=1, initial_delay_mode=rule_mode,
        ),
    })
    backtests = app.run_backtest(
        strategy=strategy(
            algorithm_id="combined-delays", symbols=["ASSET0"],
            confluence_cards=[entry], scaling_rules=[],
        ),
        study=Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=window)], engines=[engine],
        ),
        run_configuration=BacktestRunConfiguration(
            n_workers=0, show_progress=False, continue_on_error=False,
        ),
    )
    run = next(backtests.iter_backtests()).get_backtest_run(window)
    trades = run.get_trades()
    assert len(trades) == 1
    fill_delay = 1 if engine is BacktestEngine.EVENT_DRIVEN else 0
    assert pd.Timestamp(trades[0].opened_at) == raw.index[43 + fill_delay]


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("short", [False, True])
def test_position_scope_tracks_fills_scale_ins_partial_closes_and_reentry(prepared, short):
    side = SignalSide.CLOSE_SHORT if short else SignalSide.CLOSE_LONG
    instance = strategy(confluence_cards=[position_exit_card(side=side)])
    raw = frame([1, -3, -3, -3, 1, -3, -3, -3, -3, 1])
    data = {"ASSET0/EUR": raw}
    if prepared:
        instance._indicator_engine.prepare(data)
    completion = raw.index + pd.Timedelta(hours=1)
    original = SimpleNamespace(
        id=1, is_short=short, filled_amount=1, available_amount=1,
        opened_at=completion[1], closed_at=None,
    )
    active, history = [original], [original]
    context = SimpleNamespace(
        config={}, get_open_trades=lambda **kwargs: list(active),
        get_trades=lambda **kwargs: list(history),
        has_position=lambda **kwargs: bool(active) and not short,
    )

    def evaluate(row):
        context.config[INDEX_DATETIME] = completion[row]
        state = SimpleNamespace(
            strategy=instance, context=context, data=dict(data),
            current_datetime=completion[row], trace=lambda *args: None,
        )
        EvaluateIndicatorsPhase().run(state)
        signals = list(instance.generate_signals(context, state.data))
        return signals, state.data["indicators"]["ASSET0"].cards["exit"]

    signals, payload = evaluate(3)
    assert not signals and not payload["passed"]
    assert payload["ready"]  # Indicator warm-up was not reset.
    scaled = SimpleNamespace(
        id=2, is_short=short, filled_amount=1, available_amount=1,
        opened_at=completion[4], closed_at=None,
    )
    active.append(scaled)
    history.append(scaled)
    signals, payload = evaluate(4)
    assert signals and payload["position_opened_at"] == completion[1].isoformat()
    original.closed_at = completion[5]
    active.remove(original)
    instance._indicator_engine.position_anchors.clear()
    signals, payload = evaluate(6)
    assert signals and payload["position_opened_at"] == completion[1].isoformat()
    scaled.closed_at = completion[6]
    active.clear()
    signals, payload = evaluate(7)
    assert not signals and payload["evaluation_status"] == "skipped"
    new = SimpleNamespace(
        id=3, is_short=short, filled_amount=1, available_amount=1,
        opened_at=completion[7], closed_at=None,
    )
    active.append(new)
    history.append(new)
    signals, payload = evaluate(8)
    assert not signals and payload["position_opened_at"] == completion[7].isoformat()
    signals, _ = evaluate(9)
    assert signals


@pytest.mark.parametrize("engine", [BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR])
@pytest.mark.parametrize("scope", ["market", "position"])
def test_real_backtests_do_not_reuse_exit_evidence_from_previous_positions(tmp_path, engine, scope):
    scores = [1.] * 39 + [-3.] * 21
    scores[48], scores[53] = 1., 1.
    raw = frame(scores)
    app = create_app(
        name="position-lookback", config={RESOURCE_DIRECTORY: str(tmp_path)},
    )
    app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=10000)
    csv = tmp_path / "prices.csv"
    raw.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
    app.add_data_provider(CSVOHLCVDataProvider(
        storage_path=str(csv), symbol="ASSET0/EUR", time_frame="1h",
        market="BITVAVO", warmup_window=40,
    ), priority=1)
    window = BacktestDateRange(raw.index[40].to_pydatetime(), raw.index[55].to_pydatetime())
    backtests = app.run_backtest(
        strategy=strategy(
            algorithm_id="position-lookback", symbols=["ASSET0"],
            confluence_cards=[
                card("entry", SignalSide.OPEN_LONG), position_exit_card(scope),
            ],
            scaling_rules=[],
        ),
        study=Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            backtest_windows=[BacktestWindow(train_range=window)], engines=[engine],
        ),
        run_configuration=BacktestRunConfiguration(
            capture_run_reports=engine is BacktestEngine.EVENT_DRIVEN,
            n_workers=0, show_progress=False, continue_on_error=False,
        ),
    )
    run = next(backtests.iter_backtests()).get_backtest_run(window)
    closed = [t for t in run.get_trades() if t.closed_at is not None]
    assert closed
    if scope == "position":
        assert len(closed) == 2
        fill_delay = 1 if engine is BacktestEngine.EVENT_DRIVEN else 0
        assert [pd.to_datetime(t.closed_at, utc=True) for t in closed] == [
            raw.index[49 + fill_delay], raw.index[54 + fill_delay],
        ]
        if engine is BacktestEngine.EVENT_DRIVEN:
            evaluated = [
                c for report in backtests.run_reports for c in report["confluence_scores"]
                if c["card_id"] == "exit" and c.get("evaluation_status") != "skipped"
            ]
            assert evaluated and all(c["position_opened_at"] for c in evaluated)
            assert [
                pd.to_datetime(signal["timestamp"], utc=True)
                for report in backtests.run_reports for signal in report["signals"]
                if signal["side"] == "close_long" and signal["status"] == "approved"
            ] == [raw.index[49], raw.index[54]]
            rules = [
                rule for c in evaluated for rule in c["evaluations"]
                if rule["category"] == "score" and rule["name"] == "recovered"
            ]
            assert len(rules) == len(evaluated)
            assert all(rule["lookback_scope"] == "position" for rule in rules)
    else:
        assert any(pd.to_datetime(t.closed_at, utc=True) < raw.index[49] for t in closed)


class FillExecutor(Executor):
    def _long_buy(self, intent, context, metadata):
        if context.decline:
            return None
        order = SimpleNamespace(metadata=metadata)
        trade = SimpleNamespace(
            id=len(context.fills), orders=[order], is_short=False,
            available_amount=intent.amount, filled_amount=intent.amount,
            opened_at=context.config[INDEX_DATETIME],
        )
        context.trades.append(trade)
        context.history.append(trade)
        context.fills.append((context.tick, intent.quote_amount, metadata))
        context.cash -= intent.quote_amount
        return order

    def _long_sell(self, intent, context, metadata):
        raise AssertionError("This fixture only opens long entries")


class EventContext:
    def __init__(self):
        self.trades = []
        self.history = []
        self.fills = []
        self.cash = 10000.
        self.tick = 0
        self.decline = False
        self.config = {}

    def get_open_trades(self, target_symbol=None):
        return list(self.trades)

    def get_trades(self, target_symbol=None, opened_since=None):
        return [
            trade for trade in self.history
            if opened_since is None or trade.opened_at >= opened_since
        ]

    def get_portfolio(self):
        return SimpleNamespace(
            get_unallocated=lambda: self.cash,
            allocated=10000. - self.cash,
        )

    def get_trading_symbol(self):
        return "EUR"

    def get_latest_price(self, symbol):
        return 100.

    def get_unallocated(self):
        return self.cash

    def get_portfolio_value(self):
        return 10000.


def event_run(scores, *, decline=(), cooldowns=(), exposure=80):
    instance = strategy(
        executor=FillExecutor(), cooldowns=cooldowns,
        exposure_rule=ExposureRule(max_portfolio_percentage=exposure),
        phases=[
            EvaluateIndicatorsPhase(), CollectSignalsPhase(),
            ResolveConflictsPhase(), SizePositionsPhase(),
            ApplyRiskBudgetPhase(), EmitOrdersPhase(), RecordCooldownPhase(),
        ],
    )
    instance.has_open_orders = lambda symbol: False
    instance.has_position = lambda symbol: bool(context.trades)
    instance.get_position = lambda symbol: SimpleNamespace(
        amount=sum(trade.available_amount for trade in context.trades),
    )
    context = EventContext()
    raw = frame(scores)
    for i, now in enumerate(raw.index):
        context.tick = i
        context.decline = i in decline
        context.config[INDEX_DATETIME] = now
        instance.run_strategy(context, {"ASSET0/EUR": raw.iloc[:i + 1]})
    return instance, context


def vector_run(scores, *, hedge=False, dynamic=False, cooldowns=()):
    service, arguments = workload(len(scores), 1)
    raw = service.data_provider_service.get_vectorized_backtest_data()["ASSET0/EUR"]
    raw.loc[:, ["Open", "High", "Low", "Close"]] = 100.
    raw["score"] = scores
    arguments["strategy"] = strategy(cooldowns=cooldowns)
    arguments["portfolio_configuration"] = PortfolioConfiguration(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        position_mode="hedge" if hedge else "netting",
        trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=0)],
    )
    arguments["execution_backend"] = "python"
    arguments["dynamic_position_sizing"] = dynamic
    return service.run(**arguments)


@pytest.mark.parametrize("mode, exit_row", [("continuous", 8), ("recheck", 6)])
@pytest.mark.parametrize("scope", ["market", "position"])
@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("hedge", [False, True])
@pytest.mark.parametrize("dynamic", [False, True])
@pytest.mark.parametrize("rule_delay", [False, True])
def test_vector_delayed_exits_follow_fill_and_schedule(mode, exit_row, scope, short, hedge, dynamic, rule_delay):
    service, arguments = workload(12, 1)
    raw = service.data_provider_service.get_vectorized_backtest_data()["ASSET0/EUR"]
    raw.loc[:, ["Open", "High", "Low", "Close"]] = 100.
    raw["score"] = [1., -3., -3., 1., -3., 1., 1., 1., 1., 1., 1., 1.]
    entry_side = SignalSide.OPEN_SHORT if short else SignalSide.OPEN_LONG
    exit_side = SignalSide.CLOSE_SHORT if short else SignalSide.CLOSE_LONG
    exit_card = replace(
        position_exit_card(scope, exit_side), initial_delay=0 if rule_delay else 2, initial_delay_mode=mode,
        rules={"recovered": IndicatorRule(
            "zscore", 0, {"primary": 1}, comparison="ge", output_column="zscore",
            lookback_scope=scope, lookback_period=1,
            initial_delay=2 if rule_delay else 0, initial_delay_mode=mode,
        )},
    )
    arguments["strategy"] = strategy(
        confluence_cards=[card("entry", entry_side), exit_card], scaling_rules=[],
    )
    arguments["portfolio_configuration"] = PortfolioConfiguration(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        position_mode="hedge" if hedge else "netting",
        trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=0)],
    )
    arguments["execution_backend"] = "python"
    arguments["dynamic_position_sizing"] = dynamic
    run = service.run(**arguments)
    assert len(run.trades) == 1
    assert run.trades[0].is_short == short
    assert run.trades[0].opened_at == raw.index[2]
    assert run.trades[0].closed_at == raw.index[exit_row]


@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("hedge", [False, True])
@pytest.mark.parametrize("dynamic", [False, True])
def test_vector_position_scope_uses_each_legs_first_fill(short, hedge, dynamic):
    scores = [1., -3., -3., -3., -3., 1., -3., -3., 1., -3., -3., -3.]
    service, arguments = workload(len(scores), 1)
    raw = service.data_provider_service.get_vectorized_backtest_data()["ASSET0/EUR"]
    raw.loc[:, ["Open", "High", "Low", "Close"]] = 100.
    raw["score"] = scores
    arguments["strategy"] = strategy(
        confluence_cards=[
            card("entry", SignalSide.OPEN_SHORT if short else SignalSide.OPEN_LONG),
            position_exit_card(side=SignalSide.CLOSE_SHORT if short else SignalSide.CLOSE_LONG),
        ], scaling_rules=[],
    )
    arguments["portfolio_configuration"] = PortfolioConfiguration(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        position_mode="hedge" if hedge else "netting",
        trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=0)],
    )
    arguments["execution_backend"] = "auto"
    arguments["dynamic_position_sizing"] = dynamic
    run = service.run(**arguments)
    closed = [t for t in run.trades if t.closed_at is not None]
    assert [t.closed_at for t in closed] == [raw.index[6], raw.index[9]]
    assert all(t.is_short == short for t in run.trades)
    assert arguments["strategy"]._vector_indicator_engine is None


def test_position_scope_rejects_strict_native_execution_explicitly():
    from investing_algorithm_framework.infrastructure.services.backtesting.vector_native import (
        NativeExecutionUnsupported, native_events,
    )
    with pytest.raises(NativeExecutionUnsupported, match="Position-scoped"):
        native_events(
            {"ASSET0": {"position_exit_evaluators": {"exit": object()}}},
            0, 10000., SimpleNamespace(),
            dynamic_position_sizing=False, hedge_mode=False, deposit_events=[],
        )


def calculate_with_release(frame):
    return frame.assign(zscore=frame["score"], release=frame["release"])


def test_vector_position_scope_remembers_post_entry_evidence_across_scale_ins():
    service, arguments = workload(12, 1)
    raw = service.data_provider_service.get_vectorized_backtest_data()["ASSET0/EUR"]
    raw.loc[:, ["Open", "High", "Low", "Close"]] = 100.
    raw["score"] = [1., -3., -3., 1., -3., -3., -3.] + [-1.] * 5
    raw["release"] = [0.] * 7 + [1.] * 5
    exit_card = ConfluenceScoreConfig(
        id="exit", side=SignalSide.CLOSE_LONG, rules={
            "recovered": IndicatorRule(
                "zscore", 0, {"primary": 1}, output_column="zscore",
                comparison="ge", lookback_period=14, lookback_scope="position",
            ),
            "released": IndicatorRule(
                "zscore", 1, {"secondary": 1}, output_column="release", comparison="ge",
            ),
        }, group_thresholds={"primary": 1, "secondary": 1},
    )
    instance = strategy(
        indicator_configs=[config(
            calculate=calculate_with_release, output_columns=["zscore", "release"],
        )],
        confluence_cards=[
            card("entry", SignalSide.OPEN_LONG),
            card("first", SignalSide.SCALE_IN, -2.2, 0),
            card("second", SignalSide.SCALE_IN, -2.4, 1),
            exit_card,
        ],
    )
    arguments.update(strategy=instance, execution_backend="python")
    run = service.run(**arguments)
    assert [t.opened_at for t in run.trades] == [raw.index[2], raw.index[5], raw.index[7]]
    # The existing scaling cooldown defers the qualified exit by one bar.
    assert [t.closed_at for t in run.trades] == [raw.index[9]] * 3


def test_position_scope_candidates_require_an_explicit_fill_aware_consumer():
    from investing_algorithm_framework.infrastructure.services.backtesting.vector_backtest_service import (
        VectorBacktestService,
    )
    instance = strategy(confluence_cards=[position_exit_card()], scaling_rules=[])
    worker = pickle.loads(pickle.dumps(instance))
    assert worker.confluence_cards[0].rules["recovered"].lookback_scope == "position"
    candidates = list(worker.generate_signal_series({"ASSET0/EUR": frame([-3] * 4)}))
    assert any(s.metadata.get("position_scoped_lookback") for s in candidates)
    with pytest.raises(ValueError, match="fill-driven"):
        VectorBacktestService._bucket_signal_series(candidates)
    context = SimpleNamespace(
        config={INDEX_DATETIME: frame([-3] * 4).index[-1]},
        get_open_trades=lambda **kwargs: [], has_position=lambda **kwargs: True,
    )
    with pytest.raises(ValueError, match="asset holdings"):
        list(instance.generate_signals(context, {"ASSET0/EUR": frame([-3] * 4)}))


@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("prepared", [False, True])
def test_position_scope_keeps_entry_anchor_while_close_reserves_entire_trade(short, prepared):
    side = SignalSide.CLOSE_SHORT if short else SignalSide.CLOSE_LONG
    instance = strategy(confluence_cards=[position_exit_card(side=side)])
    raw = frame([-3, -3, 1, -3])
    data = {"ASSET0/EUR": raw}
    if prepared:
        instance._indicator_engine.prepare(data)
    trade = SimpleNamespace(
        id=1, is_short=short, filled_amount=1, available_amount=0,
        opened_at=raw.index[1], closed_at=None,
    )
    context = SimpleNamespace(
        config={INDEX_DATETIME: raw.index[-1] + pd.Timedelta(hours=1)},
        get_open_trades=lambda **kwargs: [trade],
        get_trades=lambda **kwargs: [trade],
        has_position=lambda **kwargs: False,
    )
    options = instance.get_confluence_evaluation_options(context)
    assert options["position_opened_at"]["ASSET0"]["exit"] == trade.opened_at
    assert not options["inactive_cards"]["ASSET0"]
    signals = list(instance.generate_signals(context, data))
    assert any(signal.side is side for signal in signals)


def test_scale_in_stage_survives_full_close_reservation_until_trade_is_closed():
    instance = strategy()
    now = pd.Timestamp("2025-01-01", tz="UTC")
    first = SimpleNamespace(
        id=1, is_short=False, filled_amount=1, available_amount=1,
        opened_at=now, orders=[],
    )
    second = SimpleNamespace(
        id=2, is_short=False, filled_amount=1, available_amount=1,
        opened_at=now + pd.Timedelta(hours=1), orders=[],
    )
    active = [first, second]
    context = SimpleNamespace(
        get_open_trades=lambda **kwargs: list(active),
        get_trades=lambda **kwargs: list(active),
    )
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    seen = set(instance._indicator_engine.entry_ids["ASSET0"])
    first.available_amount = second.available_amount = 0
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    assert instance._indicator_engine.entry_ids["ASSET0"] == seen
    first.available_amount = second.available_amount = 1
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    active.clear()
    assert instance._next_scale_in_stage(context, "ASSET0") is None
    assert "ASSET0" not in instance._indicator_engine.entry_ids


def test_event_position_scope_and_persisted_reports_survive_trailing_stop(tmp_path):
    raw = frame([1.] * 40 + [-3.] * 3 + [-1.] * 9)
    close = [100.] * 42 + [110.] * 2 + [90.] * 8
    for column in ("Open", "High", "Low", "Close"):
        raw[column] = close
    csv = tmp_path / "prices.csv"
    raw.rename_axis("Datetime").to_csv(csv)
    app = create_app(config={RESOURCE_DIRECTORY: tmp_path / "resources"})
    app.add_data_provider(CSVOHLCVDataProvider(
        storage_path=str(csv), symbol="ASSET0/EUR", market="BITVAVO",
        time_frame="1h", pandas=True,
    ))
    instance = strategy(
        algorithm_id="position-stop", strategy_id="position-stop",
        confluence_cards=[
            card("entry", SignalSide.OPEN_LONG), position_exit_card(),
        ],
        scaling_rules=[],
        stop_losses=[StopLossRule(
            percentage_threshold=7, sell_percentage=100, trailing=True,
            symbol="ASSET0",
        )],
    )
    study = Study(
        name="position-stop", initial_capital=1000,
        universe=Universe(symbols=["ASSET0"], trading_symbol="EUR", market="BITVAVO"),
        engines=[BacktestEngine.EVENT_DRIVEN],
        backtest_windows=[BacktestWindow(train_range=BacktestDateRange(
            name="stop", start_date=raw.index[40].to_pydatetime(),
            end_date=raw.index[-1].to_pydatetime(),
        ))],
    )
    result = app.run_backtest(
        strategies=[instance], study=study,
        run_configuration=BacktestRunConfiguration(
            event_state_backend="memory", n_workers=0, continue_on_error=False,
            show_progress=False, fill_missing_data=False, use_checkpoints=False,
            capture_run_reports=True, persist_run_reports=True,
            backtest_storage_directory=tmp_path / "backtests",
        ),
    )
    run = result.get_backtest(instance.algorithm_id).get_runs(engine="event")[0]
    trades = list(run.trades)
    assert len(trades) == 1
    assert pd.Timestamp(trades[0].opened_at) == raw.index[42]
    assert pd.Timestamp(trades[0].closed_at) == raw.index[45]
    reports = result.load_run_reports()
    assert any(report["stop_losses"] for report in reports)
    assert any(
        record.get("position_opened_at") == raw.index[42].isoformat()
        for report in reports for record in report["confluence_scores"]
    )


def test_public_base_and_legacy_card_support_are_preserved():
    assert issubclass(ConfluenceScoringStrategy, TradingStrategy)
    assert callable(TradingStrategy.generate_signals_from_cards)
    assert strategy().get_scaling_rule("ASSET0").initial_entry_percentage == 20


@pytest.mark.parametrize("bindings", [
    {"data_source": {"BTC": "BTC/EUR", "ETH": "ETH/EUR"}},
    {"data_sources": ["BTC/EUR", "ETH/EUR"]},
    {"data_sources": [source("BTC"), source("ETH")]},
])
def test_inspection_cards_bind_symbols_sides_stages_and_actual_sources(bindings):
    instance = strategy(
        symbols=["BTC", "ETH"], data_sources=[source("BTC"), source("ETH")],
        indicator_configs=[config(**bindings)],
        confluence_cards=[
            card("entry", SignalSide.OPEN_LONG, initial_delay=2, initial_delay_mode="recheck"),
            card("first", SignalSide.SCALE_IN, -2.2, 0),
            card("second", SignalSide.SCALE_IN, -2.4, 1),
            replace(position_exit_card(), symbols=["BTC"]),
        ],
    )
    cards = instance.get_confluence_score_cards(merge_symbols=False)
    assert len(cards) == 7
    assert len({(item.symbol, item.side, item.scale_in_stage) for item in cards}) == 7
    for item in cards:
        assert isinstance(item, ConfluenceScoreCard)
        assert item.configuration is not None
        assert item.indicator_configs["zscore"].data_source == f"{item.symbol}/EUR"
        assert item.indicator_configs["zscore"].symbol == f"{item.symbol}/EUR"
        assert item.indicator_configs["zscore"].timeframe == "1h"
        assert item.indicator_configs["zscore"].data_sources is None
        assert set(item.data_sources) == {f"{item.symbol}/EUR"}
        text = str(item)
        assert text.startswith("+=") and text.endswith("+")
        assert f"Symbol: {item.symbol}" in text
        assert f"Side: {item.side.value}" in text
        assert f"Stage: {item.scale_in_stage}" in text
        assert f"Source: {item.symbol}/EUR" in text
        assert "BITVAVO | 1h" in text
        assert "primary: sum; score >= 1; capacity=1" in text
        assert "oversold == true" not in text
        if item.side is SignalSide.SCALE_IN:
            assert f"zscore.zscore <= {-2.2 - 0.2 * item.scale_in_stage:g}" in text
        elif item.side is SignalSide.CLOSE_LONG:
            assert "zscore.zscore >= 0" in text
            assert "Lookback: 14 native bars (position)" in text
        else:
            assert "zscore.zscore <= -2" in text
            assert "Card delay: 2 evaluations (recheck)" in text
            assert "Delay: 0 evaluations (continuous)" in text


def test_inspection_merges_identical_cards_and_preserves_each_symbol_source():
    instance = strategy(
        symbols=["ETH", "BTC"], data_sources=[source("BTC"), source("ETH")],
        confluence_cards=[
            card("entry", SignalSide.OPEN_LONG),
            card("first", SignalSide.SCALE_IN, -2.2, 0),
            card("second", SignalSide.SCALE_IN, -2.4, 1),
            replace(position_exit_card(), symbols=["BTC"]),
        ],
    )
    cards = instance.get_confluence_score_cards()
    assert len(cards) == 4
    assert len(instance.get_confluence_score_cards(merge_symbols=False)) == 7
    for item in cards[:3]:
        assert item.symbol is None
        assert item.symbols == ("ETH", "BTC")
        assert item.side in (SignalSide.OPEN_LONG, SignalSide.SCALE_IN)
        assert len(item.symbol_cards) == 2
        text = str(item)
        assert "Symbols: ETH, BTC" in text
        assert "Source (ETH): ETH/EUR | ETH/EUR" in text
        assert "Source (BTC): BTC/EUR | BTC/EUR" in text
        assert len({len(line) for line in text.splitlines()}) == 1
        copied = pickle.loads(pickle.dumps(item))
        assert copied.symbols == item.symbols and str(copied) == text
        for bound in item.symbol_cards:
            assert bound.configuration is not None
            assert bound.symbol in item.symbols
            assert bound.to_dict() == item.to_dict()
    assert cards[-1].symbol == "BTC"
    assert cards[-1].symbols == ("BTC",)
    assert "Symbol: BTC" in str(cards[-1])
    assert cards[-1].side is SignalSide.CLOSE_LONG
    assert [(item.side, item.scale_in_stage) for item in cards[:3]] == [
        (SignalSide.OPEN_LONG, None), (SignalSide.SCALE_IN, 0), (SignalSide.SCALE_IN, 1),
    ]
    assert all(
        card.symbol_cards is None and card.configuration is None
        for engine in instance._indicator_engine.engines.values()
        for card in engine.compiled_cards.values()
    )


def test_inspection_does_not_merge_different_bound_timeframes():
    instance = strategy(
        symbols=["BTC", "ETH"],
        data_sources=[source("BTC"), replace(source("ETH"), time_frame="2h")],
    )
    cards = instance.get_confluence_score_cards()
    assert len(cards) == 6
    assert all(item.symbol_cards is None for item in cards)
    assert {item.symbols for item in cards} == {("BTC",), ("ETH",)}


def test_inspection_keeps_opaque_parameter_snapshots_separate_without_comparing_arrays():
    import numpy as np

    instance = strategy(
        symbols=["BTC", "ETH"], data_sources=[source("BTC"), source("ETH")],
        indicator_configs=[config(parameters={"levels": np.array([1, 2])})],
    )
    cards = instance.get_confluence_score_cards()
    assert len(cards) == 6
    assert all(item.symbol_cards is None for item in cards)


@pytest.mark.parametrize("change", ["threshold", "delay", "parameters", "weight", "source"])
def test_merged_inspection_rejects_different_card_definitions(change):
    first = strategy(
        data_sources=[source("BTC")], confluence_cards=[card("entry", SignalSide.OPEN_LONG)],
        scaling_rules=[],
    ).get_confluence_score_cards()[0]
    entry = card("entry", SignalSide.OPEN_LONG)
    indicator, data_source = config(), source("ETH")
    if change == "threshold":
        entry = card("entry", SignalSide.OPEN_LONG, -3)
    elif change == "delay":
        entry = replace(entry, initial_delay=2)
    elif change == "parameters":
        indicator = config(parameters={"period": 20})
    elif change == "weight":
        entry = replace(entry, rules={
            "oversold": replace(entry.rules["oversold"], group_weights={"primary": 2}),
        })
    else:
        data_source = replace(data_source, headers={"X-Mode": "different"})
    second = strategy(
        data_sources=[data_source], indicator_configs=[indicator],
        confluence_cards=[entry], scaling_rules=[],
    ).get_confluence_score_cards()[0]
    with pytest.raises(ValueError, match="identical"):
        replace(
            first, symbol=None, configuration=None, indicator_configs=None,
            data_sources=None, symbol_cards=(first, second),
        )


def test_inspection_is_lazy_and_does_not_change_engine_scoring_or_state():
    from investing_algorithm_framework.services.indicator_engine import IndicatorEngine

    with patch.object(IndicatorEngine, "get_confluence_score_cards") as inspect_cards:
        instance = strategy()
        raw = {"ASSET0/EUR": frame([-3] * 4)}
        before = list(instance.generate_signal_series(raw))
        inspect_cards.assert_not_called()
    engine = instance._indicator_engine.engines["ASSET0"]
    compiled = dict(engine.compiled_cards)
    cards = instance.get_confluence_score_cards()
    assert all(item.configuration is None for item in compiled.values())
    for item in cards:
        assert item.to_dict() == compiled[item.name].to_dict()
        assert item == compiled[item.name]
    assert all(engine.compiled_cards[name] is item for name, item in compiled.items())
    after = list(instance.generate_signal_series(raw))
    for original, current in zip(before, after):
        pd.testing.assert_series_equal(original.series, current.series)


def test_inspection_lists_rules_per_group_with_group_specific_weights():
    base = card("entry", SignalSide.OPEN_LONG)
    rule = base.rules["oversold"]
    definitions = {
        "primary_only": replace(rule, group_weights={"primary": 1, "total": 1}),
        "secondary_only": replace(rule, group_weights={"secondary": 2, "total": 2}),
        "shared": replace(rule, group_weights={"primary": 3, "secondary": 4, "total": 3}),
        "negative": replace(rule, group_weights={"secondary": -1, "total": -1}),
    }
    instance = strategy(
        indicator_configs=[config(parameters={"period": 14})],
        confluence_cards=[replace(
            base, rules=definitions,
            group_aggregation={"primary": "max", "secondary": "sum", "total": "sum"},
            group_thresholds={"total": 2},
        )], scaling_rules=[],
    )
    item = instance.get_confluence_score_cards()[0]
    text = str(item)
    content = "\n".join(
        line[2:-2].rstrip() for line in text.splitlines() if line.startswith("|")
    )
    sections = content.split("Group ")[1:]
    assert len(sections) == 3
    assert "Rules:" not in content and "Groups:" not in content
    for section, group in zip(sections, ("primary", "secondary", "total")):
        assert section.startswith(f"{group}:")
        expected = [name for name, rule in definitions.items() if group in rule.group_weights]
        displayed = [
            line.strip().split(":")[0] for line in section.splitlines()
            if line.startswith("  ") and not line.startswith("    ")
        ]
        assert displayed == expected
        for name in expected:
            weight = definitions[name].group_weights[group]
            assert f"  {name}: zscore.zscore <= -2\n    Weight: {weight:g}" in section
        assert section.count("Lookback: 1 native bars (market)") == len(expected)
        assert section.count("Source: ASSET0/EUR") == len(expected)
        assert section.count("Parameters: {'period': 14}") == len(expected)
    assert "Group primary: max; optional; capacity=3" in content
    assert "Group secondary: sum; optional; capacity=6" in content
    assert "Group total: sum; score >= 2; capacity=6" in content
    assert item.to_dict() == instance._indicator_engine.engines["ASSET0"].compiled_cards["entry"].to_dict()


def test_inspection_snapshots_are_isolated_picklable_and_show_bounds_and_parameters():
    instance = strategy(
        indicator_configs=[config(parameters={"period": 14})],
        confluence_cards=[replace(
            card("entry", SignalSide.OPEN_LONG),
            rules={"oversold": IndicatorRule(
                "zscore", -2, {"primary": 1}, output_column="zscore",
                lower_bound=-3, upper_bound=-1, lookback_period=2,
            )},
        )], scaling_rules=[],
    )
    item = instance.get_confluence_score_cards()[0]
    text = str(item)
    content = " ".join(
        line[2:-2].strip() for line in text.splitlines() if line.startswith("|")
    )
    assert "zscore.zscore <= -2 AND zscore.zscore >= -3 AND zscore.zscore <= -1" in content
    assert len({len(line) for line in text.splitlines()}) == 1
    assert "Lookback: 2 native bars (market)" in text
    assert "Parameters: {'period': 14}" in text
    copied = pickle.loads(pickle.dumps(item))
    assert str(copied) == text
    assert copied.side is SignalSide.OPEN_LONG
    with pytest.raises(TypeError):
        item.indicator_configs["other"] = item.indicator_configs["zscore"]
    with pytest.raises(TypeError):
        item.data_sources["other"] = item.data_sources["ASSET0/EUR"]
    with pytest.raises(FrozenInstanceError):
        item.data_sources["ASSET0/EUR"].market = "CHANGED"
    engine = instance._indicator_engine.engines["ASSET0"]
    assert item.configuration is not engine.cards["entry"]
    assert item.indicator_configs["zscore"] is not engine.configs["zscore"]
    assert item.data_sources["ASSET0/EUR"] is not engine.data_sources["ASSET0/EUR"]
    assert instance.get_confluence_score_cards()[0].data_sources["ASSET0/EUR"].market == "BITVAVO"
    assert instance.data_sources[0].market == "BITVAVO"


@pytest.mark.parametrize("kind, parameters", [
    ("rsi", "period=14"),
    ("z_score", "period=14, scale=1"),
    ("macd", "short=12, long=26, signal=9"),
    ("stochastic", "period=14, k_slowing=3, d_period=3"),
])
def test_inspection_displays_builtin_indicator_parameters_and_default_outputs(kind, parameters):
    indicator = IndicatorConfig(id="built_in", indicator=kind, timeframe="1h")
    output = indicator.outputs[-1] if len(indicator.outputs) > 1 else None
    instance = strategy(
        indicator_configs=[indicator],
        confluence_cards=[ConfluenceScoreConfig(
            id="entry", side=SignalSide.OPEN_LONG,
            rules={"signal": IndicatorRule(
                "built_in", 0, {"primary": 1}, output_column=output,
            )}, group_thresholds={"primary": 1},
        )], scaling_rules=[],
    )
    item = instance.get_confluence_score_cards()[0]
    text = str(item)
    content = " ".join(
        line[2:-2].strip() for line in text.splitlines() if line.startswith("|")
    )
    assert f"Indicator: {kind}; {parameters}" in content
    assert f"built_in.{output or indicator.outputs[0]} <= 0" in content


def test_shared_scaling_rules_bind_to_each_confluence_symbol():
    symbols = ["ASSET0", "ASSET1"]
    instance = strategy(
        symbols=symbols, data_sources=[source(symbol) for symbol in symbols],
        position_sizes=[PositionSize(
            symbols=symbols, percentage_of_portfolio=20,
        )],
        scaling_rules=[ScalingRule(
            symbols=symbols, max_entries=3,
            initial_entry_percentage=20, scale_in_percentage=[40, 40],
        )],
    )
    assert set(instance._indicator_engine.engines) == set(symbols)
    assert instance.get_scaling_rule("ASSET0") is instance.get_scaling_rule(
        "ASSET1",
    )
    copied = pickle.loads(pickle.dumps(instance))
    assert copied.get_position_size("ASSET1").symbols == tuple(symbols)


def test_declarations_and_strategy_remain_worker_picklable():
    instance = strategy()
    copied = pickle.loads(pickle.dumps(instance))
    declared = copied._indicator_engine.engines["ASSET0"].cards["first"]
    assert declared.side is SignalSide.SCALE_IN
    assert declared.scale_in_stage == 0
    assert declared.symbols == ()
    raw = {"ASSET0/EUR": frame([-3] * 4)}
    original_masks = list(instance.generate_signal_series(raw))
    copied_masks = list(copied.generate_signal_series(raw))
    for original, copy in zip(original_masks, copied_masks):
        pd.testing.assert_series_equal(original.series, copy.series)
    with pytest.raises(TypeError):
        declared.rules["other"] = declared.rules["oversold"]


def test_builtin_indicator_aliases_still_share_a_calculation():
    first = IndicatorConfig(
        "first", indicator="ema", period=2, timeframe="1h",
    )
    second = replace(first, id="second")
    declared = ConfluenceScoreConfig(
        id="entry", side=SignalSide.OPEN_LONG,
        rules={
            name: IndicatorRule(name, 101, {"primary": 1})
            for name in ("first", "second")
        },
        group_thresholds={"primary": 2},
    )
    instance = strategy(
        indicator_configs=[first, second], confluence_cards=[declared],
    )
    native = instance._indicator_engine.engines["ASSET0"]
    assert native.calculation_count == 1
    masks = list(instance.generate_signal_series({
        "ASSET0/EUR": frame([-3] * 4),
    }))
    assert masks[0].series.tolist() == [False, False, True, True]


@pytest.mark.parametrize("hedge", [False, True])
@pytest.mark.parametrize("dynamic", [False, True])
def test_event_and_vector_fill_three_tranches_after_cooldown(hedge, dynamic):
    scores = [-3.] * 9
    instance, context = event_run(scores)
    assert [(tick, quote) for tick, quote, _ in context.fills] == [
        (1, 800), (3, 1600), (5, 1600),
    ]
    assert context.fills[1][2]["scale_in_stage"] == 0
    assert context.fills[2][2]["scale_in_stage"] == 1
    assert "decision_trace" in context.fills[0][2]
    assert not any(signal.side is SignalSide.SCALE_IN for signal in instance.last_signals)
    run = vector_run(scores, hedge=hedge, dynamic=dynamic)
    assert [trade.cost for trade in run.trades] == pytest.approx([800, 1600, 1600])
    assert [pd.Timestamp(trade.opened_at).hour for trade in run.trades] == [1, 3, 5]


@pytest.mark.parametrize("hedge", [False, True])
def test_expired_threshold_is_not_replayed_when_cooldown_ends(hedge):
    scores = [-2.1, -3, -1, -1, -1, -3, -3, -3, -3]
    _, context = event_run(scores)
    assert [tick for tick, _, _ in context.fills] == [1, 6, 8]
    run = vector_run(scores, hedge=hedge)
    assert [pd.Timestamp(trade.opened_at).hour for trade in run.trades] == [1, 6, 8]


def test_declined_order_does_not_consume_stage_or_start_cooldown():
    _, context = event_run([-3.] * 9, decline=(3,))
    assert [(tick, quote) for tick, quote, _ in context.fills] == [
        (1, 800), (4, 1600), (6, 1600),
    ]


@pytest.mark.parametrize("hedge", [False, True])
def test_explicit_cooldown_rule_takes_priority_over_thresholds(hedge):
    cooldowns = [CooldownRule(trigger="buy", blocks="buy", bars=3)]
    _, context = event_run([-3.] * 12, cooldowns=cooldowns)
    run = vector_run([-3.] * 12, cooldowns=cooldowns, hedge=hedge)
    expected = [tick for tick, _, _ in context.fills]
    assert expected == [1, 4, 7]
    assert [pd.Timestamp(trade.opened_at).hour for trade in run.trades] == expected


def test_event_exposure_cap_is_still_applied():
    _, context = event_run([-3.] * 9, exposure=20)
    assert [quote for _, quote, _ in context.fills] == pytest.approx([800, 1200])


def test_partial_lot_closure_does_not_rearm_stages_and_full_exit_resets():
    instance = strategy()
    context = EventContext()
    first = SimpleNamespace(
        id=1, is_short=False, available_amount=1, orders=[],
        filled_amount=1, opened_at=pd.Timestamp("2025-01-01", tz="UTC"),
    )
    second = SimpleNamespace(
        id=2, is_short=False, available_amount=1,
        orders=[SimpleNamespace(metadata={"scale_in_stage": 0})],
        filled_amount=1, opened_at=pd.Timestamp("2025-01-02", tz="UTC"),
    )
    context.trades = [first]
    assert instance._next_scale_in_stage(context, "ASSET0") == 0
    context.trades.append(second)
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    context.trades.remove(second)
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    context.trades.clear()
    assert instance._next_scale_in_stage(context, "ASSET0") is None
    context.trades = [first]
    assert instance._next_scale_in_stage(context, "ASSET0") == 0
    resumed = strategy()
    context.trades = [second]
    assert resumed._next_scale_in_stage(context, "ASSET0") == 1


def test_lot_filled_and_closed_between_ticks_still_advances_stage():
    instance = strategy()
    context = EventContext()
    initial = SimpleNamespace(
        id=1, is_short=False, available_amount=1, filled_amount=1,
        opened_at=pd.Timestamp("2025-01-01", tz="UTC"), orders=[],
    )
    context.trades = [initial]
    context.history = [initial]
    assert instance._next_scale_in_stage(context, "ASSET0") == 0
    context.history.append(SimpleNamespace(
        id=2, is_short=False, available_amount=0, filled_amount=1,
        opened_at=pd.Timestamp("2025-01-02", tz="UTC"),
        orders=[SimpleNamespace(metadata={"scale_in_stage": 0})],
    ))
    assert instance._next_scale_in_stage(context, "ASSET0") == 1
    assert instance._next_scale_in_stage(context, "ASSET0") == 1


@pytest.mark.parametrize("bindings", [
    {"data_source": {"BTC": "BTC/EUR", "ETH": "ETH/EUR"}},
    {"data_sources": ["BTC/EUR", "ETH/EUR"]},
    {"data_sources": [source("BTC"), source("ETH")]},
])
def test_symbol_bindings_are_isolated_and_empty_symbols_apply_to_all(bindings):
    instance = strategy(
        data_sources=[source("BTC"), source("ETH")],
        indicator_configs=[config(**bindings)],
    )
    raw = {"BTC/EUR": frame([-3] * 4), "ETH/EUR": frame([-1] * 4)}
    masks = list(instance.generate_signal_series(raw))
    assert any(mask.series.any() for mask in masks if mask.symbol == "BTC")
    assert not any(mask.series.any() for mask in masks if mask.symbol == "ETH")
    scoped = strategy(
        data_sources=[source("BTC"), source("ETH")],
        indicator_configs=[config(data_source="BTC/EUR")],
        confluence_cards=[card("entry", SignalSide.OPEN_LONG, symbols=["btc"])],
    )
    assert set(scoped._indicator_engine.engines) == {"BTC"}


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("execution", ["precompute", "per_decision"])
def test_plural_source_event_evaluations_are_symbol_isolated(
    prepared, execution,
):
    instance = strategy(
        symbols=["BTC", "ETH"],
        data_sources=[source("BTC"), source("ETH")],
        indicator_configs=[config(
            data_sources=["BTC/EUR", "ETH/EUR"], execution=execution,
        )],
        confluence_cards=[card("entry", SignalSide.OPEN_LONG)],
        scaling_rules=[],
    )
    raw = {"BTC/EUR": frame([-3] * 4), "ETH/EUR": frame([-1] * 4)}
    if prepared:
        instance._indicator_engine.prepare(raw)
    if execution == "precompute":
        masks = list(instance.generate_signal_series(raw))
    for now in raw["BTC/EUR"].index:
        context = SimpleNamespace(config={INDEX_DATETIME: now})
        signals = list(instance.generate_signals(
            context, {key: value.loc[:now] for key, value in raw.items()},
        ))
        expected = {("BTC", SignalSide.OPEN_LONG)} if now.hour else set()
        assert {(item.symbol, item.side) for item in signals} == expected
        if execution == "precompute":
            assert {
                (item.symbol, item.side) for item in masks
                if item.series.loc[now]
            } == expected
    copied = pickle.loads(pickle.dumps(instance))
    assert copied._indicator_engine.required_windows == {
        "BTC/EUR": 1, "ETH/EUR": 1,
    }


def test_plural_source_bindings_reject_unknown_and_ambiguous_sources():
    with pytest.raises(ValueError, match="Unknown data source: missing"):
        strategy(indicator_configs=[config(
            data_sources=["ASSET0/EUR", "missing"],
        )])
    duplicate_symbol = DataSource(
        identifier="other", symbol="ASSET0/EUR",
        data_type="ohlcv", time_frame="1h",
    )
    with pytest.raises(ValueError, match="exactly one"):
        strategy(
            data_sources=[source(), duplicate_symbol],
            indicator_configs=[config(
                data_sources=["ASSET0/EUR", "other"],
            )],
        )


def test_precompute_is_once_and_only_completed_candles_are_used():
    calls = Mock(side_effect=calculate)
    instance = strategy(indicator_configs=[config(calculate=calls)])
    raw = frame([-3, -3, -3, -3])
    masks = list(instance.generate_signal_series({"ASSET0/EUR": raw}))
    calls.assert_called_once()
    assert masks[0].series.tolist() == [False, True, True, True]
    assert instance._indicator_engine.entry_counts == {}


def test_event_preparation_replaces_run_local_state():
    instance = strategy()
    old = instance._indicator_engine
    old.entry_counts["ASSET0"] = 3
    raw = frame([-3] * 4)
    provider = Mock()
    provider.get_backtest_data.return_value = raw
    service = EventBacktestService(provider, None, None, None, None, None, None, None)
    service.prepare_indicators(
        SimpleNamespace(strategies=[instance]),
        SimpleNamespace(start_date=raw.index[1], end_date=raw.index[-1]),
    )
    assert instance._indicator_engine is not old
    assert instance._indicator_engine.entry_counts == {}


@pytest.mark.parametrize("engine", [
    BacktestEngine.EVENT_DRIVEN, BacktestEngine.VECTOR,
])
@pytest.mark.parametrize("plural", [False, True])
def test_real_app_backtest_executes_the_declared_ladder(
    tmp_path, engine, plural,
):
    raw = frame([-3] * 60)
    symbols = ["ASSET0", "ASSET1"] if plural else ["ASSET0"]
    app = create_app(
        name="confluence-ladder", config={RESOURCE_DIRECTORY: str(tmp_path)},
    )
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
    )
    for symbol in symbols:
        csv = tmp_path / f"{symbol}.csv"
        data = raw if symbol == "ASSET0" else frame([-1] * 60)
        data.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
        app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv), symbol=f"{symbol}/EUR", time_frame="1h",
            market="BITVAVO", warmup_window=40,
        ), priority=1)
    window = BacktestDateRange(
        start_date=raw.index[40].to_pydatetime(),
        end_date=raw.index[55].to_pydatetime(),
    )
    study = Study(
        universe=Universe(market="BITVAVO", trading_symbol="EUR"),
        backtest_windows=[BacktestWindow(train_range=window)],
        engines=[engine],
    )
    backtests = app.run_backtest(
        strategy=strategy(
            algorithm_id="confluence-ladder", symbols=symbols,
            data_sources=[source(symbol) for symbol in symbols],
            indicator_configs=[config(
                data_sources=[f"{symbol}/EUR" for symbol in symbols],
            )] if plural else [config()],
            confluence_cards=[
                card("entry", SignalSide.OPEN_LONG),
                card("first", SignalSide.SCALE_IN, -2.2, 0),
                card("second", SignalSide.SCALE_IN, -2.4, 1),
                card("exit", SignalSide.CLOSE_LONG, -100),
            ],
        ),
        study=study,
        run_configuration=BacktestRunConfiguration(
            capture_run_reports=engine is BacktestEngine.EVENT_DRIVEN,
            n_workers=0, show_progress=False, continue_on_error=False,
        ),
    )
    if engine is BacktestEngine.EVENT_DRIVEN:
        assert backtests.run_reports
        for report in backtests.run_reports:
            assert len(report["confluence_scores"]) == 4 * len(symbols)
            assert {
                item["card_id"] for item in report["confluence_scores"]
            } == {"entry", "first", "second", "exit"}
            assert len(report["data_sources"]) == len(symbols)
            assert all(
                item["timestamp"] == report["timestamp"]
                and item["strategy_id"] in report["strategy_ids"]
                and item["decision_trace"]["entries"]
                for item in report["confluence_scores"]
            )
            assert all(
                item["source_timestamp"] < item["timestamp"]
                and item["values"]["Close"] == 100
                for item in report["data_sources"]
            )
            assert len(report["indicators"]) == len(symbols)
            assert {
                item["symbol"]: item["value"]
                for item in report["indicators"]
            } == {
                symbol: -3 if symbol == "ASSET0" else -1
                for symbol in symbols
            }
            assert all(
                item["name"] == "zscore.zscore"
                and item["timestamp"] == report["timestamp"]
                and item["strategy_id"] in report["strategy_ids"]
                for item in report["indicators"]
            )
            for item in report["confluence_scores"]:
                if item.get("evaluation_status") == "skipped":
                    assert item["card_id"] == "exit"
                    assert item["signal_status"] == "not_triggered"
                    assert item["signal_reason"] == "confluence.long_exit_requires_position"
                    assert not {"score", "qualified", "evaluations"} & item.keys()
                    assert not any(
                        signal["symbol"] == item["symbol"]
                        and signal["side"] == "close_long"
                        for signal in report["signals"]
                    )
                    continue
                emitted = next((
                    signal for signal in report["signals"]
                    if signal["symbol"] == item["symbol"]
                    and signal["side"] == item["side"]
                    and signal["source"] == item["card_id"]
                ), None)
                if emitted is not None:
                    assert item["signal_status"] == emitted["status"]
                    assert item["signal_reason"] == emitted["reason"]
                    assert item["signal_strength"] == emitted["strength"]
                    if emitted["status"] == "approved":
                        if item["side"] == "open_long":
                            assert item["position_before"]["side"] == "flat"
                        elif item["side"] == "scale_in":
                            assert item["position_before"]["side"] == "long"
                            assert item["position_before"]["long_entries"] == item["scale_in_stage"] + 1
                else:
                    assert item["signal_status"] == "not_emitted"
                    assert item["signal_reason"]
                    assert item["signal_strength"] is None
                assert item["maximum_score"] == 1
                assert item["position_before"]["maximum_entries"] == 3
                scored = next(row for row in item["evaluations"] if row["category"] == "score")
                assert scored["weight"] == 1
                assert scored["value"] == (-3 if item["symbol"] == "ASSET0" else -1)
                assert scored["threshold"] in (-2, -2.2, -2.4, -100)
                assert scored["time_frame"] == "1h"
        cards = [
            item for report in backtests.run_reports
            for item in report["confluence_scores"]
        ]
        assert any(
            item.get("qualified") and item["signal_status"] == "rejected"
            and item["signal_reason"] == "resolve_conflicts.state_block_open"
            for item in cards
        )
        for reason in (
            "confluence.scale_in_requires_position",
            "confluence.scale_in_stage_inactive",
            "confluence.scale_in_stage_completed",
        ):
            assert any(
                item.get("qualified") and item["signal_status"] == "not_emitted"
                and item["signal_reason"] == reason
                for item in cards
            )
        assert any(item["signal_status"] == "not_triggered" for item in cards)
        assert any(
            item["card_id"] == "exit" and "score" in item
            for item in cards
        )
    run = next(backtests.iter_backtests()).get_backtest_run(window)
    assert [trade.cost for trade in run.get_trades()] == pytest.approx([
        800, 1600, 1600,
    ])
    assert {trade.target_symbol for trade in run.get_trades()} == {"ASSET0"}


def test_vector_rejects_non_precomputed_callable_explicitly():
    instance = strategy(indicator_configs=[config(execution="per_decision")])
    with pytest.raises(ValueError, match="execution='precompute'"):
        list(instance.generate_signal_series({"ASSET0/EUR": frame([-3] * 4)}))


def test_card_actions_are_explicit_and_never_inferred_from_ids():
    declared = card("arbitrary_name", SignalSide.OPEN_LONG)
    instance = strategy(confluence_cards=[declared])
    masks = list(instance.generate_signal_series({"ASSET0/EUR": frame([-3] * 4)}))
    assert {mask.side for mask in masks} == {
        SignalSide.OPEN_LONG, SignalSide.CLOSE_LONG, SignalSide.SCALE_IN,
    }
    assert not next(mask for mask in masks if mask.side is SignalSide.SCALE_IN).series.any()
    with pytest.raises(ValueError, match="explicit side"):
        strategy(confluence_cards=[replace(declared, side=None)])


def test_non_scaling_strategy_does_not_query_trade_history_for_signals():
    instance = strategy(confluence_cards=[
        card("entry", SignalSide.OPEN_LONG),
    ])
    raw = frame([-3] * 4)
    context = SimpleNamespace(
        config={INDEX_DATETIME: raw.index[-1]},
        get_open_trades=Mock(side_effect=AssertionError("Unnecessary query")),
        get_trades=Mock(side_effect=AssertionError("Unnecessary query")),
    )
    signals = list(instance.generate_signals(context, {"ASSET0/EUR": raw}))
    assert len(signals) == 1
    context.get_open_trades.assert_not_called()
    context.get_trades.assert_not_called()


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("side", [SignalSide.CLOSE_LONG, SignalSide.CLOSE_SHORT])
def test_exit_cards_skip_scoring_until_matching_position_opens(prepared, side):
    from investing_algorithm_framework.services.run_reports.snapshot import (
        confluence_score_snapshots,
    )

    exit_card = card("exit", side)
    exit_card = replace(exit_card, rules={
        "oversold": replace(exit_card.rules["oversold"], lookback_period=3),
    })
    instance = strategy(confluence_cards=[
        card("entry", SignalSide.OPEN_LONG), exit_card,
    ])
    raw = {"ASSET0/EUR": frame([-3] * 4)}
    if prepared:
        instance._indicator_engine.prepare(raw)
    native = instance._indicator_engine.engines["ASSET0"]
    context = SimpleNamespace(
        config={}, get_open_trades=Mock(return_value=[]),
        has_position=Mock(return_value=False),
    )
    phase = EvaluateIndicatorsPhase()
    with patch.object(native, "_score_card", wraps=native._score_card) as score:
        for timestamp, trades in (
            (raw["ASSET0/EUR"].index[1], []),
            (raw["ASSET0/EUR"].index[2], [
                SimpleNamespace(is_short=side is SignalSide.CLOSE_LONG),
            ]),
        ):
            context.config[INDEX_DATETIME] = timestamp
            context.get_open_trades.return_value = trades
            state = SimpleNamespace(
                strategy=instance, context=context, data=dict(raw),
                current_datetime=timestamp, trace=Mock(),
            )
            phase.run(state)
            signals = list(instance.generate_signals(context, state.data))
            assert all(signal.side is not side for signal in signals)
            evaluations = state.data["indicators"]
            skipped = evaluations["ASSET0"].cards["exit"]
            assert skipped["evaluation_status"] == "skipped"
            assert "score" not in skipped
            assert evaluations["ASSET0"].values["zscore"]["zscore"] == -3
            captures = instance._indicator_engine.confluence_snapshot(evaluations)
            record, = [
                item for item in confluence_score_snapshots(
                    evaluated=captures, signals=[],
                ) if item["card_id"] == "exit"
            ]
            assert record["signal_status"] == "not_triggered"
            assert record["signal_reason"] == (
                "confluence.long_exit_requires_position"
                if side is SignalSide.CLOSE_LONG else
                "confluence.short_exit_requires_position"
            )
            assert not {"score", "qualified", "groups", "evaluations"} & record.keys()
        assert all(call.args[0] != "exit" for call in score.call_args_list)

    context.config[INDEX_DATETIME] = raw["ASSET0/EUR"].index[-1]
    context.get_open_trades.return_value = [
        SimpleNamespace(is_short=side is SignalSide.CLOSE_SHORT),
    ]
    state = SimpleNamespace(
        strategy=instance, context=context, data=dict(raw),
        current_datetime=context.config[INDEX_DATETIME], trace=Mock(),
    )
    phase.run(state)
    signals = list(instance.generate_signals(context, state.data))
    assert any(signal.side is side for signal in signals)
    payload = state.data["indicators"]["ASSET0"].cards["exit"]
    assert payload["qualified"]
    assert payload["lookback_ready"]["oversold"]
    assert payload["score"] == 1
    context.get_open_trades.return_value = []
    signals = list(instance.generate_signals(context, dict(raw)))
    assert all(signal.side is not side for signal in signals)


def test_asset_holdings_without_open_trade_still_allow_long_exit():
    instance = strategy(confluence_cards=[card("exit", SignalSide.CLOSE_LONG)])
    raw = {"ASSET0/EUR": frame([-3] * 4)}
    context = SimpleNamespace(
        config={INDEX_DATETIME: raw["ASSET0/EUR"].index[-1]},
        get_open_trades=Mock(return_value=[]),
        has_position=Mock(return_value=True),
    )
    assert [signal.side for signal in instance.generate_signals(context, raw)] == [
        SignalSide.CLOSE_LONG,
    ]


def test_supplied_diagnostic_evaluations_do_not_emit_exit_when_flat():
    instance = strategy(confluence_cards=[card("exit", SignalSide.CLOSE_LONG)])
    raw = {"ASSET0/EUR": frame([-3] * 4)}
    now = raw["ASSET0/EUR"].index[-1]
    context = SimpleNamespace(
        config={INDEX_DATETIME: now},
        get_open_trades=Mock(return_value=[]),
        has_position=Mock(return_value=False),
    )
    evaluations = instance._indicator_engine.evaluate(raw, now)
    assert evaluations["ASSET0"].cards["exit"]["qualified"]
    assert not list(instance.generate_signals(context, {
        **raw, "indicators": evaluations,
    }))
    assert evaluations["ASSET0"].cards["exit"]["evaluation_status"] == "skipped"


def test_vector_preparation_handles_empty_native_history():
    masks = list(strategy().generate_signal_series({
        "ASSET0/EUR": frame([]),
    }))
    assert masks
    assert all(mask.series.empty and mask.series.dtype == bool for mask in masks)


@pytest.mark.parametrize("stage", [-1, True, 1.5])
def test_invalid_stage_is_rejected(stage):
    with pytest.raises(ValueError, match="nonnegative integer"):
        card("bad", SignalSide.SCALE_IN, stage=stage)


def test_invalid_bindings_and_entry_capacity_fail_early():
    with pytest.raises(ValueError, match="Duplicate card action"):
        strategy(confluence_cards=[
            card("a", SignalSide.OPEN_LONG), card("b", SignalSide.OPEN_LONG),
        ])
    with pytest.raises(ValueError, match="contiguous"):
        strategy(confluence_cards=[card("bad", SignalSide.SCALE_IN, stage=1)])
    with pytest.raises(ValueError, match="max_entries=3"):
        strategy(scaling_rules=[ScalingRule(max_entries=2)])
    with pytest.raises(ValueError, match="Card symbols"):
        strategy(confluence_cards=[card("bad", SignalSide.OPEN_LONG, symbols=["ETH"])])


@pytest.mark.parametrize("value", [0, -1, 101, True, float("nan")])
def test_invalid_initial_entry_percentage_is_rejected(value):
    with pytest.raises(ValueError, match="initial_entry_percentage"):
        ScalingRule(initial_entry_percentage=value)
