"""Mean-variance Markowitz: monthly long-only min-variance optimisation."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
from scipy.optimize import minimize

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
LOOKBACK = 90
REBALANCE_EVERY_BARS = 30
TARGET_DAILY_RETURN = 0.001  # ~25% annualised


class MarkowitzStrategy(TradingStrategy):
    algorithm_id = "mean-variance-markowitz"
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

        weights = self._optimise(data)
        if weights is None:
            return
        self._rebalance(context, data, weights)

    def _optimise(self, data: Dict[str, Any]) -> Dict[str, float] | None:
        rets_matrix = []
        cols = []
        for s in SYMBOLS:
            df = data[f"{s}-ohlcv"]
            if len(df) < LOOKBACK + 1:
                continue
            r = df["Close"].pct_change().tail(LOOKBACK).dropna().to_numpy()
            if len(r) < LOOKBACK - 5:
                continue
            rets_matrix.append(r)
            cols.append(s)
        if len(cols) < 2:
            return None

        n = min(len(r) for r in rets_matrix)
        R = np.vstack([r[-n:] for r in rets_matrix])
        mu = R.mean(axis=1)
        cov = np.cov(R) + np.eye(len(cols)) * 1e-6

        def variance(w):
            return float(w @ cov @ w)

        cons = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "ineq", "fun": lambda w: float(w @ mu)
             - TARGET_DAILY_RETURN},
        ]
        bounds = [(0.0, 1.0) for _ in cols]
        x0 = np.ones(len(cols)) / len(cols)
        res = minimize(variance, x0, method="SLSQP",
                       bounds=bounds, constraints=cons)
        if not res.success:
            # Fallback: equal-weight if QP infeasible.
            w = x0
        else:
            w = np.clip(res.x, 0, None)
            if w.sum() == 0:
                return None
            w = w / w.sum()
        return dict(zip(cols, w.tolist()))

    def _rebalance(
        self, context: Context, data: Dict[str, Any],
        weights: Dict[str, float],
    ) -> None:
        equity = context.get_unallocated()
        for sym in self.symbols:
            if context.has_position(sym, market=self.market):
                pos = context.get_position(sym, market=self.market)
                price = float(data[f"{sym}/EUR-ohlcv"]["Close"].iloc[-1])
                equity += pos.get_amount() * price

        for symbol, weight in weights.items():
            sym = symbol.split("/")[0]
            price = float(data[f"{symbol}-ohlcv"]["Close"].iloc[-1])
            if price <= 0:
                continue
            target_amount = (equity * weight) / price
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
