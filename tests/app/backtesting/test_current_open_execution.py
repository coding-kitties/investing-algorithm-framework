"""Real-engine acceptance for explicit session-open market execution."""

from datetime import datetime, timezone

import pandas as pd
import polars as pl
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from investing_algorithm_framework import (
    INDEX_DATETIME,
    BacktestDateRange,
    BacktestRunConfiguration,
    BacktestWindow,
    DataSource,
    DataType,
    MarketOrderExecutor,
    PandasOHLCVDataProvider,
    PositionSize,
    Schedule,
    Signal,
    SignalSide,
    Study,
    TimeUnit,
    TradingStrategy,
    Universe,
    create_app,
    SimulationBlotter,
    FixedSlippage,
    FixedCommission,
    FillModel,
)


class OpenOnlyProvider(PandasOHLCVDataProvider):
    """A session-open feed: the current session has no completed HLCV."""

    def get_backtest_data(self, backtest_index_date, *args, **kwargs):
        frame = self.data.filter(pl.col("Datetime") <= backtest_index_date)
        if frame is None or frame.is_empty():
            return frame
        current = pl.col("Datetime") == backtest_index_date
        return frame.with_columns(
            *[
                pl.when(current)
                .then(pl.col("Open"))
                .otherwise(pl.col(c))
                .alias(c)
                for c in ("High", "Low", "Close")
            ],
            pl.when(current)
            .then(0)
            .otherwise(pl.col("Volume"))
            .alias("Volume"),
        )

    def copy(self, data_source):
        return type(self)(
            self.data.to_pandas(),
            symbol=data_source.symbol,
            market=data_source.market,
            time_frame=data_source.time_frame,
        )


class HalfFill(FillModel):
    def get_fill_amount(self, order_amount, available_volume=None):
        return order_amount / 2


class NeverFill(FillModel):
    def get_fill_amount(self, order_amount, available_volume=None):
        return 0


def run_example(
    tmp_path,
    *,
    current_open=True,
    initial_capital=10000,
    costs=False,
    volume_limited=False,
    partial=False,
    allocation=10,
    precision=0,
    direct=False,
):
    frame = pd.DataFrame(
        [
            (10, 11, 9, 10),
            (10, 12, 9, 11),
            (11, 14, 10, 13),
            (15, 20, 15, 20),
            (20, 30, 10, 14),
            (12, 13, 11, 12),
        ],
        columns=["Open", "High", "Low", "Close"],
    )
    frame.insert(
        0, "Datetime", pd.date_range("2026-01-05", periods=6, tz="UTC")
    )
    frame["Volume"] = 10000.0

    class Example(TradingStrategy):
        def __init__(self):
            super().__init__(
                strategy_id="session-open",
                symbols=["AAA"],
                schedule=Schedule.every(1, TimeUnit.DAY),
                data_sources=[
                    DataSource(
                        identifier="AAA",
                        symbol="AAA/DKK",
                        data_type=DataType.OHLCV,
                        market="TEST",
                        time_frame="1d",
                    )
                ],
                position_sizes=[
                    PositionSize(percentage_of_portfolio=allocation)
                ],
                executor=MarketOrderExecutor(
                    precision=precision,
                    fill_at_current_open=current_open,
                ),
            )

        def generate_signals(self, context, data):
            now = context.get_config()[INDEX_DATETIME]
            if now.day == 8:
                if direct:
                    context.create_market_order(
                        target_symbol="AAA", order_side="BUY",
                        percentage_of_portfolio=allocation,
                        precision=precision, fill_at_current_open=True,
                    )
                else:
                    yield Signal("AAA", SignalSide.OPEN_LONG)
            if now.day == 10 and context.get_open_trades():
                yield Signal("AAA", SignalSide.CLOSE_LONG)

    app = create_app(config={"RESOURCE_DIRECTORY": str(tmp_path)})
    if costs:
        app.set_blotter(
            SimulationBlotter(
                slippage_model=FixedSlippage(1),
                commission_model=FixedCommission(2),
            )
        )
    if volume_limited:
        app.set_blotter(SimulationBlotter(fill_model=NeverFill()))
    if partial:
        app.set_blotter(
            SimulationBlotter(
                fill_model=HalfFill(),
                slippage_model=FixedSlippage(1),
                commission_model=FixedCommission(2),
            )
        )
    app.add_data_provider(
        OpenOnlyProvider(
            frame,
            symbol="AAA/DKK",
            market="TEST",
            time_frame="1d",
        )
    )
    app.add_market(
        market="TEST", trading_symbol="DKK", initial_balance=initial_capital
    )
    study = Study(
        name="current-open",
        universe=Universe(market="TEST", trading_symbol="DKK"),
        initial_capital=initial_capital,
        backtest_windows=[
            BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=frame.Datetime.iloc[0].to_pydatetime(),
                    end_date=frame.Datetime.iloc[-1].to_pydatetime(),
                    name="example",
                )
            )
        ],
    )
    results = app.run_backtest(
        strategy=Example(), study=study,
        run_configuration=BacktestRunConfiguration(fill_missing_data=False),
    )
    return next(results.iter_backtests()).get_runs("event")[0]


class TestCurrentOpenExecution(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)

    def test_current_open_fills_whole_shares_and_final_session_exit(self):
        tmp_path = self.tmp_path
        run = run_example(tmp_path)
        assert len(run.orders) == 2
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert [buy.amount, sell.amount] == [66, 66]
        assert [buy.price, sell.price] == [15, 12]
        assert (
            buy.created_at
            == buy.updated_at
            == datetime(2026, 1, 8, tzinfo=timezone.utc)
        )
        assert (
            sell.created_at
            == sell.updated_at
            == datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        assert [buy.status, sell.status] == ["CLOSED", "CLOSED"]
        assert len(run.trades) == 1
        trade = run.trades[0]
        assert trade.opened_at == buy.created_at
        assert trade.closed_at == sell.created_at
        self.assertAlmostEqual(trade.net_gain, -198)
        self.assertAlmostEqual(run.backtest_metrics.final_value, 9802)
        positions = {p.symbol: p.amount for p in run.positions}
        assert positions["AAA"] == 0
        assert positions["DKK"] == 9802

    def test_current_open_skips_allocation_below_one_share(self):
        tmp_path = self.tmp_path
        run = run_example(tmp_path, initial_capital=100)
        assert run.orders == []
        assert run.trades == []
        assert run.backtest_metrics.final_value == 100

    def test_current_open_uses_native_slippage_and_commission(self):
        tmp_path = self.tmp_path
        run = run_example(tmp_path, costs=True)
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert [buy.amount, sell.amount] == [66, 66]
        assert [buy.price, sell.price] == [16, 11]
        assert [buy.order_fee, sell.order_fee] == [2, 2]
        self.assertAlmostEqual(run.backtest_metrics.final_value, 9666)

    def test_current_open_cancels_unfilled_remainder_without_later_fill(self):
        tmp_path = self.tmp_path
        run = run_example(tmp_path, volume_limited=True)
        assert len(run.orders) == 1
        order = run.orders[0]
        assert order.status == "CANCELED"
        assert order.filled == 0
        assert order.updated_at == order.created_at
        assert run.trades == []
        assert run.backtest_metrics.final_value == 10000

    def test_default_market_orders_still_wait_for_next_tick(self):
        run = run_example(self.tmp_path, current_open=False)
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert buy.created_at.day == 8
        assert buy.updated_at.day == 9
        assert sell.status == "OPEN"

    def test_partial_fills_keep_whole_units_prices_and_cash(self):
        run = run_example(self.tmp_path, partial=True)
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert [buy.filled, sell.filled] == [33, 16]
        assert [buy.price, sell.price] == [16, 11]
        assert [buy.order_fee, sell.order_fee] == [2, 2]
        assert [buy.status, sell.status] == ["CANCELED", "CANCELED"]
        positions = {p.symbol: p.amount for p in run.positions}
        assert positions["AAA"] == 17
        assert positions["DKK"] == 9644

    def test_current_open_whole_share_fill_fits_cash_after_costs(self):
        run = run_example(self.tmp_path, initial_capital=96,
                          allocation=100, costs=True)
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert buy.filled == sell.filled == 5
        assert buy.status == "CANCELED"
        self.assertAlmostEqual(run.backtest_metrics.final_value, 67)

    def test_unaffordable_fill_without_precision_is_canceled(self):
        run = run_example(self.tmp_path, initial_capital=96,
                          allocation=100, costs=True, precision=None)
        assert len(run.orders) == 1
        assert run.orders[0].status == "CANCELED"
        assert run.orders[0].filled == 0
        assert run.trades == []
        self.assertAlmostEqual(run.backtest_metrics.final_value, 96)

    def test_direct_current_open_order_preserves_precision(self):
        run = run_example(self.tmp_path, initial_capital=96,
                          allocation=100, costs=True, direct=True)
        buy, sell = sorted(run.orders, key=lambda order: order.created_at)
        assert buy.filled == sell.filled == 5
        self.assertAlmostEqual(run.backtest_metrics.final_value, 67)
