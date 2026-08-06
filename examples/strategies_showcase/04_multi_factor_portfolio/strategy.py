"""Multi-factor portfolio: momentum + low-vol + liquidity gate."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from investing_algorithm_framework import (
    AverageDollarVolume,
    Context,
    DataSource,
    Pipeline,
    PositionSize,
    Returns,
    Signal,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    Volatility,
    Schedule,
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
    schedule = Schedule.every(1, TimeUnit.DAY)
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

    position_sizes = [
        PositionSize(
            symbol=symbol.split("/")[0],
            percentage_of_portfolio=(100.0 / TOP_N) - 0.5,
        )
        for symbol in SYMBOLS
    ]

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        screen = data["FactorScreen"]
        if screen.is_empty():
            return

        targets_df = screen.sort("alpha", descending=True).head(TOP_N)
        target_bases = {
            row["symbol"].split("/")[0]
            for row in targets_df.iter_rows(named=True)
        }

        for symbol in SYMBOLS:
            base = symbol.split("/")[0]
            if base in target_bases:
                continue
            if not context.has_position(base, market=self.market):
                continue
            yield Signal(
                symbol=base, side=SignalSide.CLOSE_LONG,
                source="multi-factor",
            )

        for base in target_bases:
            if context.has_position(base, market=self.market):
                continue
            yield Signal(
                symbol=base, side=SignalSide.OPEN_LONG,
                source="multi-factor",
            )
