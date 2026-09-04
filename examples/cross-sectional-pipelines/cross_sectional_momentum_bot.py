"""Pipeline API — cross-sectional momentum trading bot (Phase 1).

This example shows how to turn a :class:`Pipeline` screen into an actual
trading bot that rebalances a portfolio every day into the top-N
momentum names within a liquid universe.

What it does on each iteration (once per day):

1. The framework builds a long-form OHLCV panel across the configured
   symbols.
2. ``MomentumScreener`` ranks every symbol by 30-day return within the
   top-3 most liquid names (by 30-day average dollar volume).
3. ``CrossSectionalMomentumBot.generate_signals`` reads the resulting
   ``polars.DataFrame`` from ``data["MomentumScreener"]``, picks the
   top-2 ranked symbols, and emits typed :class:`Signal` objects:
     * ``CLOSE_LONG`` for any held position no longer in the target set,
     * ``OPEN_LONG`` for any new target.

   The framework's phase pipeline turns those signals into orders.
   Per-symbol sizing is declared once via the ``position_sizes`` class
   attribute (equal-weight ``1 / TOP_N`` of the portfolio).

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
    BacktestWindow,
    Context,
    DataSource,
    DEFAULT_LOGGING_CONFIG,
    Pipeline,
    PositionSize,
    Returns,
    Signal,
    SignalSide,
    Study,
    TimeUnit,
    TradingStrategy,
    Universe,
    create_app,
    Schedule,
)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
load_dotenv()


SYMBOLS = [
    "BTC/EUR",
    "ETH/EUR",
    "SOL/EUR",
    "ADA/EUR",
    "XRP/EUR",
    "DOT/EUR",
    "LINK/EUR",
]
TOP_N = 2
MARKET = "bitvavo"
TRADING_SYMBOL = "EUR"


class MomentumScreener(Pipeline):
    """Rank the most liquid 3 names by 30-day return."""

    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)
    universe = dollar_volume.top(3)
    alpha = momentum.rank(mask=universe)


class CrossSectionalMomentumBot(TradingStrategy):
    algorithm_id = "pipeline-momentum-bot"
    schedule = Schedule.every(1, TimeUnit.DAY)
    market = MARKET
    symbols = SYMBOLS

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

    pipelines = [MomentumScreener]

    position_sizes = [
        PositionSize(
            symbol=symbol.split("/")[0],
            percentage_of_portfolio=(100.0 / TOP_N) - 0.5,
        )
        for symbol in SYMBOLS
    ]

    def generate_signals(self, context: Context, data: Dict[str, Any]):
        screen = data["MomentumScreener"]

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
            yield Signal(symbol=base, side=SignalSide.CLOSE_LONG, source="csm")

        for base in target_bases:
            if context.has_position(base, market=self.market):
                continue
            yield Signal(symbol=base, side=SignalSide.OPEN_LONG, source="csm")


app = create_app()
app.add_strategy(CrossSectionalMomentumBot)
app.add_market(market=MARKET, trading_symbol=TRADING_SYMBOL, initial_balance=1000)


if __name__ == "__main__":
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365)

    study = Study(
        name="cross-sectional-momentum",
        universe=Universe(
            symbols=SYMBOLS,
            market=MARKET,
            trading_symbol=TRADING_SYMBOL,
            initial_capital=1000,
        ),
        backtest_windows=[
            BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=start,
                    end_date=end,
                )
            )
        ],
    )
    backtests = app.run_backtest(
        strategy=CrossSectionalMomentumBot,
        study=study,
    )
    backtest = backtests[0]
    metrics = backtest.get_backtest_metrics(study_name=study.name)
    print(metrics)
