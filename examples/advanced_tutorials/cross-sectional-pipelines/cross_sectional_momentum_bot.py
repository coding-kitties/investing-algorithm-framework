"""Pipeline API — cross-sectional momentum trading bot (Phase 1).

This example shows how to turn a :class:`Pipeline` screen into an actual
trading bot that rebalances a portfolio every day into the top-N
momentum names within a liquid universe.

What it does on each iteration (once per day):

1. The framework builds a long-form OHLCV panel across the configured
   symbols.
2. ``MomentumScreener`` ranks every symbol by 30-day return within the
   top-3 most liquid names (by 30-day average dollar volume).
3. ``CrossSectionalMomentumBot.run_strategy`` reads the resulting
   ``polars.DataFrame`` from ``data["MomentumScreener"]``, picks the
   top-2 ranked symbols, and rebalances the portfolio:
     * closes any open position that is no longer in the target set,
     * opens an equal-weight market order for any new target.

Backtest the bot:

.. code-block:: bash

    python examples/cross-sectional-pipelines/cross_sectional_momentum_bot.py

Run it live by removing the ``app.run_backtest(...)`` block and calling
``app.run()`` instead. Bitvavo does not require API keys for market
data, so the backtest works out of the box.

See docs:
- ``docs/Advanced Concepts/pipelines.md``
- ``docs/Advanced Concepts/pipelines-event-backtest.md``
"""
from __future__ import annotations

import logging.config
from datetime import datetime, timedelta
from typing import Any, Dict

from dotenv import load_dotenv

from investing_algorithm_framework import (
    AverageDollarVolume,
    BacktestDateRange,
    Context,
    DataSource,
    DEFAULT_LOGGING_CONFIG,
    OrderSide,
    OrderType,
    Pipeline,
    Returns,
    TimeUnit,
    TradingStrategy,
    create_app,
)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
load_dotenv()


# Universe
# A small crypto basket. All symbols quote in EUR so they share the
# same trading symbol (the portfolio currency below).
SYMBOLS = [
    "BTC/EUR",
    "ETH/EUR",
    "SOL/EUR",
    "ADA/EUR",
    "XRP/EUR",
    "DOT/EUR",
    "LINK/EUR",
]

#: Number of symbols held simultaneously.
TOP_N = 2

#: Exchange and quote currency for the bot.
MARKET = "bitvavo"
TRADING_SYMBOL = "EUR"


# Pipeline: declarative cross-sectional screen
class MomentumScreener(Pipeline):
    """Rank the most liquid 3 names by 30-day return."""

    # Per-symbol factors. Each becomes an output column.
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)

    # The master mask: only the 3 most liquid names enter ranking.
    universe = dollar_volume.top(3)

    # Cross-sectional rank within the universe (highest momentum gets
    # the highest rank).
    alpha = momentum.rank(mask=universe)


# Strategy: rebalance into the top-N pipeline picks
class CrossSectionalMomentumBot(TradingStrategy):
    algorithm_id = "pipeline-momentum-bot"
    time_unit = TimeUnit.DAY
    interval = 1
    market = MARKET
    trading_symbol = TRADING_SYMBOL
    symbols = SYMBOLS

    # OHLCV data sources, one per symbol. ``warmup_window`` covers the
    # longest factor lookback (30) plus a buffer so the pipeline starts
    # producing values from bar 1 of the backtest. Tickers are added so
    # the bot can read live bid/ask in production — in backtest mode the
    # framework will fall back to the latest OHLCV close.
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

    # Opt-in to the Pipeline API. The framework will compute this every
    # iteration and place the result under ``data["MomentumScreener"]``.
    pipelines = [MomentumScreener]

    # Strategy entry point
    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        screen = data["MomentumScreener"]

        # Skip iterations where the universe / warmup is not satisfied.
        if screen.is_empty():
            return

        # Rank is ascending — highest rank = highest momentum.
        targets_df = screen.sort("alpha", descending=True).head(TOP_N)
        targets = {row["symbol"] for row in targets_df.iter_rows(named=True)}

        def _last_close(symbol: str) -> float:
            ohlcv = data[f"{symbol}-ohlcv"]
            try:
                return float(ohlcv["Close"][-1])
            except (KeyError, TypeError):
                return float(ohlcv["close"].iloc[-1])

        def _base(symbol: str) -> str:
            # ``target_symbol`` is just the base asset (e.g. "BTC").
            return symbol.split("/")[0]

        # 1. Close positions no longer in the target set
        for symbol in SYMBOLS:
            if symbol in targets:
                continue
            base = _base(symbol)
            if not context.has_position(base, market=self.market):
                continue
            position = context.get_position(base, market=self.market)
            context.create_order(
                target_symbol=base,
                order_side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                price=_last_close(symbol),
                amount=position.get_amount(),
            )

        # 2. Open new equal-weight positions for new targets
        unallocated = context.get_unallocated()
        new_targets = [
            sym for sym in targets
            if not context.has_position(_base(sym), market=self.market)
        ]
        if not new_targets:
            return

        per_target_budget = unallocated / len(new_targets)
        for symbol in new_targets:
            price = _last_close(symbol)
            if price <= 0:
                continue
            # 0.5% safety buffer so floating-point rounding does not
            # push the order total above the available unallocated cash.
            amount = (per_target_budget * 0.995) / price
            context.create_order(
                target_symbol=_base(symbol),
                order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=price,
                amount=amount,
            )


# App wiring
app = create_app()
app.add_strategy(CrossSectionalMomentumBot)
app.add_market(market=MARKET, trading_symbol=TRADING_SYMBOL, initial_balance=1000)


if __name__ == "__main__":
    # Backtest over the last full year. Replace with ``app.run()`` to go
    # live (requires bitvavo credentials in your .env file).
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365)
    backtest_date_range = BacktestDateRange(start_date=start, end_date=end)
    backtest = app.run_backtest(
        backtest_date_range=backtest_date_range,
    )
    # Inspect the result interactively with the BacktestReport dashboard:
    #     from investing_algorithm_framework import BacktestReport
    #     BacktestReport(backtest).show()
    print(backtest)
