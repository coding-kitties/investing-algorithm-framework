"""Pipeline API — momentum cross-sectional screener example.

Phase 1 of the Pipeline API (#501) lets a strategy compute factors
across all of its OHLCV symbols in one shot, then receive a wide
``DataFrame`` (one row per surviving symbol, one column per factor)
on each iteration.

This example screens a small crypto basket every day for the two
highest-momentum symbols by 30-day return, ranked within the top-3
liquidity universe. It does not place any orders — it only prints the
screen output, so you can see what the pipeline produces.

Phase 1 only supports the **event-driven backtest** runner; live
pipelines are not implemented yet. Run the example with:

.. code-block:: bash

    python examples/cross-sectional-pipelines/momentum_screener.py

See ``docs/Advanced Concepts/pipelines-event-backtest.md``.
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
    Pipeline,
    Returns,
    TimeUnit,
    TradingStrategy,
    create_app,
)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
load_dotenv()


SYMBOLS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR", "XRP/EUR"]
MARKET = "bitvavo"
TRADING_SYMBOL = "EUR"


class MomentumScreener(Pipeline):
    """Top-2 momentum names within the most liquid 3 of the universe."""

    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)

    universe = dollar_volume.top(3)
    alpha = momentum.rank(mask=universe)


class CrossSectionalMomentum(TradingStrategy):
    algorithm_id = "cross-sectional-momentum"
    time_unit = TimeUnit.DAY
    interval = 1
    market = MARKET
    trading_symbol = TRADING_SYMBOL
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

    def run_strategy(self, context: Context, data: Dict[str, Any]):
        screen = data["MomentumScreener"]
        if screen is None or screen.is_empty():
            return
        # Pick the top 2 by alpha rank (highest rank = highest momentum
        # within the liquidity universe).
        top = screen.sort("alpha", descending=True).head(2)
        for row in top.iter_rows(named=True):
            print(
                f"{row['symbol']}: 30d return = {row['momentum']:.2%}, "
                f"adv = {row['dollar_volume']:.0f}, alpha rank = {row['alpha']}"
            )


app = create_app()
app.add_strategy(CrossSectionalMomentum)
app.add_market(market=MARKET, trading_symbol=TRADING_SYMBOL, initial_balance=1000)


if __name__ == "__main__":
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=120)
    backtest_date_range = BacktestDateRange(start_date=start, end_date=end)
    backtest = app.run_backtest(backtest_date_range=backtest_date_range)
    metrics = backtest.get_backtest_metrics(date_range=backtest_date_range)
    print(metrics)
