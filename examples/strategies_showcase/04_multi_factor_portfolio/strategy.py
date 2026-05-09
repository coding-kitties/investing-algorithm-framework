"""Multi-factor portfolio: momentum + low-vol + liquidity gate."""
from __future__ import annotations

from typing import Any, Dict

from investing_algorithm_framework import (
    AverageDollarVolume,
    Context,
    DataSource,
    OrderSide,
    OrderType,
    Pipeline,
    Returns,
    TimeUnit,
    TradingStrategy,
    Volatility,
)

SYMBOLS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR",
           "XRP/EUR", "DOT/EUR", "LINK/EUR"]
TOP_N = 3
MARKET = "BITVAVO"
TRADING_SYMBOL = "EUR"


class FactorScreen(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)
    vol = Volatility(window=30)

    universe = dollar_volume.top(5)
    momentum_rank = momentum.rank(mask=universe)
    low_vol_rank = (-vol).rank(mask=universe)
    alpha = momentum_rank + low_vol_rank


class MultiFactorPortfolioStrategy(TradingStrategy):
    algorithm_id = "multi-factor-portfolio"
    time_unit = TimeUnit.DAY
    interval = 1
    market = MARKET
    trading_symbol = TRADING_SYMBOL
    symbols = SYMBOLS
    pipelines = [FactorScreen]

    data_sources = [
        DataSource(
            data_type="OHLCV",
            market=MARKET,
            symbol=symbol,
            warmup_window=60,
            time_frame="1d",
            identifier=f"{symbol}-ohlcv",
        )
        for symbol in SYMBOLS
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        screen = data["FactorScreen"]
        if screen.is_empty():
            return

        targets_df = screen.sort("alpha", descending=True).head(TOP_N)
        targets = {row["symbol"] for row in targets_df.iter_rows(named=True)}

        def last_close(symbol: str) -> float:
            ohlcv = data[f"{symbol}-ohlcv"]
            try:
                return float(ohlcv["Close"][-1])
            except (KeyError, TypeError):
                return float(ohlcv["close"].iloc[-1])

        def base(symbol: str) -> str:
            return symbol.split("/")[0]

        for symbol in SYMBOLS:
            if symbol in targets:
                continue
            sym = base(symbol)
            if not context.has_position(sym, market=self.market):
                continue
            position = context.get_position(sym, market=self.market)
            context.create_order(
                target_symbol=sym,
                order_side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                price=last_close(symbol),
                amount=position.get_amount(),
            )

        unallocated = context.get_unallocated()
        new_targets = [
            s for s in targets
            if not context.has_position(base(s), market=self.market)
        ]
        if not new_targets:
            return
        per_target = unallocated / len(new_targets)
        for symbol in new_targets:
            price = last_close(symbol)
            if price <= 0:
                continue
            amount = (per_target * 0.995) / price
            context.create_order(
                target_symbol=base(symbol),
                order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=price,
                amount=amount,
            )
