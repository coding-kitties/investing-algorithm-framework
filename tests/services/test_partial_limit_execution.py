"""Partial execution must not change the remaining order's limit."""

from datetime import datetime, timedelta, timezone

import polars as pl

from investing_algorithm_framework import (
    BacktestDateRange,
    FillModel,
    FixedSlippage,
    MarketCredential,
    PortfolioConfiguration,
    SimulationBlotter,
)
from investing_algorithm_framework.domain import INDEX_DATETIME
from investing_algorithm_framework.services import (
    BacktestTradeOrderEvaluator,
    OrderBacktestService,
)
from tests.resources import TestBase


class HalfFill(FillModel):
    def get_fill_amount(self, order_amount, available_volume=None):
        return order_amount / 2


class TestPartialLimitExecution(TestBase):
    market_credentials = [
        MarketCredential(market="binance", api_key="key", secret_key="key")
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR")
    ]
    external_balances = {"EUR": 10000}

    def test_partial_fill_preserves_limit_for_later_candles(self):
        container = self.app.container
        container.order_service.override(
            OrderBacktestService(
                trade_service=container.trade_service(),
                order_repository=container.order_repository(),
                position_service=container.position_service(),
                portfolio_repository=container.portfolio_repository(),
                portfolio_configuration_service=(
                    container.portfolio_configuration_service()
                ),
                portfolio_snapshot_service=(
                    container.portfolio_snapshot_service()
                ),
                configuration_service=container.configuration_service(),
            )
        )
        now = datetime(2026, 1, 8, tzinfo=timezone.utc)
        self.app.initialize_backtest_config(
            BacktestDateRange(start_date=now, end_date=now + timedelta(days=2))
        )
        config = container.configuration_service()
        config.add_value(INDEX_DATETIME, now)
        orders = container.order_service()
        order = orders.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "amount": 10,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CREATED",
        })
        evaluator = BacktestTradeOrderEvaluator(
            trade_service=container.trade_service(),
            order_service=orders,
            trade_stop_loss_service=container.trade_stop_loss_service(),
            trade_take_profit_service=container.trade_take_profit_service(),
            configuration_service=config,
            blotter=SimulationBlotter(
                fill_model=HalfFill(), slippage_model=FixedSlippage(1)
            ),
        )
        for offset, price in enumerate((10.0, 10.5)):
            tick = now + timedelta(days=offset)
            config.add_value(INDEX_DATETIME, tick)
            candle = pl.DataFrame({
                "Datetime": [tick],
                "Open": [price],
                "High": [price],
                "Low": [price],
                "Close": [price],
                "Volume": [100.0],
            })
            evaluator.evaluate(
                open_trades=[],
                open_orders=[orders.get(order.id)],
                ohlcv_data={"BTC/EUR": candle},
            )
            settled = orders.get(order.id)
            self.assertEqual(settled.filled, 5)
            self.assertEqual(settled.remaining, 5)
            self.assertEqual(settled.price, 10)
            self.assertEqual(settled.status, "OPEN")
