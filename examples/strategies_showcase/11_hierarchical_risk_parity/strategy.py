"""Hierarchical Risk Parity (HRP) — López de Prado, 2016."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform

from investing_algorithm_framework import (
    Context,
    DataSource,
    DataType,
    OrderSide,
    OrderType,
    TimeUnit,
    TradingStrategy,
)

SYMBOLS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR",
           "XRP/EUR", "DOT/EUR", "LINK/EUR"]
MARKET = "BITVAVO"
LOOKBACK = 90
REBALANCE_EVERY_BARS = 30


def _quasi_diag_order(link: np.ndarray) -> List[int]:
    tree = to_tree(link, rd=False)
    return tree.pre_order(lambda x: x.id)


def _cluster_var(cov: np.ndarray, items: List[int]) -> float:
    sub = cov[np.ix_(items, items)]
    iv = 1.0 / np.diag(sub)
    w = iv / iv.sum()
    return float(w @ sub @ w)


def _hrp_weights(returns: pd.DataFrame) -> pd.Series:
    cov = returns.cov().to_numpy()
    corr = returns.corr().to_numpy()
    dist = np.sqrt(0.5 * (1.0 - corr))
    np.fill_diagonal(dist, 0.0)
    link = linkage(squareform(dist, checks=False), method="single")
    order = _quasi_diag_order(link)

    weights = np.ones(len(order))
    clusters = [order]
    while clusters:
        new_clusters = []
        for c in clusters:
            if len(c) <= 1:
                continue
            split = len(c) // 2
            left, right = c[:split], c[split:]
            v_left = _cluster_var(cov, left)
            v_right = _cluster_var(cov, right)
            alpha = 1.0 - v_left / (v_left + v_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= (1.0 - alpha)
            new_clusters += [left, right]
        clusters = new_clusters

    return pd.Series(weights, index=returns.columns)


class HRPStrategy(TradingStrategy):
    algorithm_id = "hierarchical-risk-parity"
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

        cols = {}
        for s in SYMBOLS:
            df = data[f"{s}-ohlcv"]
            if len(df) >= LOOKBACK + 1:
                cols[s] = df["Close"].pct_change().tail(LOOKBACK).dropna()
        if len(cols) < 2:
            return
        returns = pd.DataFrame(cols).dropna()
        if len(returns) < LOOKBACK - 5:
            return
        weights = _hrp_weights(returns)
        weights = weights / weights.sum()

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
            target_amount = (equity * float(weight)) / price
            current = 0.0
            if context.has_position(sym, market=self.market):
                current = context.get_position(
                    sym, market=self.market
                ).get_amount()
            delta = target_amount - current
            if abs(delta * price) < 5:
                continue
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            context.create_order(
                target_symbol=sym, order_side=side,
                order_type=OrderType.LIMIT, price=price,
                amount=abs(delta),
            )
