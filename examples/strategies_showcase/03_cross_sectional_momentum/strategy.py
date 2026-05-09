"""Cross-sectional momentum strategy using the Pipeline API."""
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
)

SYMBOLS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR", "XRP/EUR"]
TOP_N = 2
MARKET = "BITVAVO"
TRADING_SYMBOL = "EUR"


class MomentumScreener(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)
    universe = dollar_volume.top(3)
    alpha = momentum.rank(mask=universe)


class CrossSectionalMomentumStrategy(TradingStrategy):
    algorithm_id = "cross-sectional-momentum"
    time_unit = TimeUnit.DAY
    interval = 1
    market = MARKET
    trading_symbol = TRADING_SYMBOL
    symbols = SYMBOLS
    pipelines = [MomentumScreener]

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
        screen = data["MomentumScreener"]
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

        # Close non-targets
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

        # Open new targets equal-weight
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
