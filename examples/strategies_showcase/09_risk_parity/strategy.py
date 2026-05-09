"""Risk parity (inverse-volatility weighting), monthly rebalance."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from investing_algorithm_framework import (
    Context,
    DataSource,
    DataType,
    OrderSide,
    OrderType,
    TimeUnit,
    TradingStrategy,
)

SYMBOLS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR", "XRP/EUR"]
MARKET = "BITVAVO"
LOOKBACK = 30
REBALANCE_EVERY_BARS = 30  # ~monthly on daily bars


class RiskParityStrategy(TradingStrategy):
    algorithm_id = "risk-parity-inv-vol"
    time_unit = TimeUnit.DAY
    interval = 1
    market = MARKET
    trading_symbol = "EUR"
    symbols = [s.split("/")[0] for s in SYMBOLS]

    data_sources = [
        DataSource(
            identifier=f"{s}-ohlcv",
            data_type=DataType.OHLCV, market=MARKET, symbol=s,
            time_frame="1d", warmup_window=LOOKBACK + 5, pandas=True,
        )
        for s in SYMBOLS
    ]

    def __init__(self):
        super().__init__()
        self._bar_count = 0

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        self._bar_count += 1
        if self._bar_count % REBALANCE_EVERY_BARS != 1:
            return

        weights = self._target_weights(data)
        if not weights:
            return
        self._rebalance(context, data, weights)

    def _target_weights(self, data: Dict[str, Any]) -> Dict[str, float]:
        inv_vols: Dict[str, float] = {}
        for s in SYMBOLS:
            df = data[f"{s}-ohlcv"]
            if len(df) < LOOKBACK + 1:
                continue
            rets = df["Close"].pct_change().tail(LOOKBACK).dropna()
            sd = float(rets.std())
            if sd <= 0 or np.isnan(sd):
                continue
            inv_vols[s] = 1.0 / sd
        if not inv_vols:
            return {}
        total = sum(inv_vols.values())
        return {s: w / total for s, w in inv_vols.items()}

    def _rebalance(
        self, context: Context, data: Dict[str, Any],
        weights: Dict[str, float],
    ) -> None:
        equity = context.get_unallocated()
        for sym in self.symbols:
            if context.has_position(sym, market=self.market):
                pos = context.get_position(sym, market=self.market)
                price = self._last_close(data, f"{sym}/EUR")
                equity += pos.get_amount() * price

        for symbol, weight in weights.items():
            sym = symbol.split("/")[0]
            price = self._last_close(data, symbol)
            if price <= 0:
                continue
            target_value = equity * weight
            target_amount = target_value / price
            current_amount = 0.0
            if context.has_position(sym, market=self.market):
                current_amount = context.get_position(
                    sym, market=self.market
                ).get_amount()
            delta = target_amount - current_amount
            if abs(delta * price) < 5:
                continue
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            context.create_order(
                target_symbol=sym, order_side=side,
                order_type=OrderType.LIMIT, price=price,
                amount=abs(delta),
            )

    @staticmethod
    def _last_close(data: Dict[str, Any], symbol: str) -> float:
        df = data[f"{symbol}-ohlcv"]
        return float(df["Close"].iloc[-1])
