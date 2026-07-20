"""Vector-mode cross-sectional momentum bot.

This is the vector-backtest twin of
``cross_sectional_momentum_bot.py``. It implements the same idea —
hold the top-N momentum names within a liquid universe, rebalanced
daily — but expressed as a single ``generate_signal_series`` pass
over the full window instead of a per-iteration ``generate_signals``
loop.

Key differences from the event-mode version:

* **No** ``Pipeline``. Phase 1 of the Pipeline API runs inside the
  event loop only; the vector runner does not yet evaluate
  pipelines. The cross-sectional rank is done inline below.
* **No** ``context`` parameter. The portfolio doesn't exist when
  ``generate_signal_series`` is called — positions and cash emerge
  as the engine plays back the declared columns. Entry/exit
  arbitration happens inside ``ResolveConflictsPhase`` per bar.
* The strategy emits **edge** signals (``OPEN_LONG`` on the bar a
  symbol *enters* the target set, ``CLOSE_LONG`` on the bar it
  *leaves*) instead of every-bar membership. The framework would
  no-op duplicate sides, but edges keep the signal stream small
  and the trace log readable.

Run with:

.. code-block:: bash

    python examples/cross-sectional-pipelines/cross_sectional_momentum_bot_vector.py
"""
from __future__ import annotations

import logging.config
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable

import pandas as pd
from dotenv import load_dotenv

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestWindow,
    DataSource,
    DEFAULT_LOGGING_CONFIG,
    PositionSize,
    Schedule,
    SignalSeries,
    SignalSide,
    Study,
    TimeUnit,
    TradingStrategy,
    Universe,
    create_app,
    signal_series_from_column,
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
LIQUIDITY_TOP = 3
MOMENTUM_WINDOW = 30
ADV_WINDOW = 30
MARKET = "bitvavo"
TRADING_SYMBOL = "EUR"


class CrossSectionalMomentumBotVector(TradingStrategy):
    algorithm_id = "pipeline-momentum-bot-vector"
    schedule = Schedule.every(1, TimeUnit.DAY)
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

    position_sizes = [
        PositionSize(
            symbol=symbol.split("/")[0],
            percentage_of_portfolio=(100.0 / TOP_N) - 0.5,
        )
        for symbol in SYMBOLS
    ]

    def _target_membership(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.DataFrame]:
        """Return per-symbol frames with `enter` and `exit` edge columns."""
        adv_wide: Dict[str, pd.Series] = {}
        momentum_wide: Dict[str, pd.Series] = {}
        per_symbol_frames: Dict[str, pd.DataFrame] = {}

        for pair in SYMBOLS:
            df = data[f"{pair}-ohlcv"].copy()
            close = df["Close"].astype(float)
            volume = df["Volume"].astype(float)
            adv_wide[pair] = (close * volume).rolling(ADV_WINDOW).mean()
            momentum_wide[pair] = close.pct_change(MOMENTUM_WINDOW)
            per_symbol_frames[pair] = df

        adv_df = pd.DataFrame(adv_wide)
        mom_df = pd.DataFrame(momentum_wide)

        liquidity_rank = adv_df.rank(axis=1, ascending=False, method="min")
        liquid_mask = liquidity_rank <= LIQUIDITY_TOP
        momentum_rank = mom_df.where(liquid_mask).rank(
            axis=1, ascending=False, method="min"
        )
        is_target = (momentum_rank <= TOP_N).fillna(False)

        prev = is_target.shift(1, fill_value=False)
        enter_df = is_target & ~prev
        exit_df = ~is_target & prev

        out: Dict[str, pd.DataFrame] = {}
        for pair in SYMBOLS:
            df = per_symbol_frames[pair]
            out[pair] = df.assign(
                enter=enter_df[pair].reindex(df.index, fill_value=False),
                exit=exit_df[pair].reindex(df.index, fill_value=False),
            )
        return out

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        frames = self._target_membership(data)
        for pair in SYMBOLS:
            base = pair.split("/")[0]
            df = frames[pair]
            yield signal_series_from_column(
                df, "enter",
                side=SignalSide.OPEN_LONG,
                symbol=base,
                source="cross-sectional-momentum-vector",
            )
            yield signal_series_from_column(
                df, "exit",
                side=SignalSide.CLOSE_LONG,
                symbol=base,
                source="cross-sectional-momentum-vector",
            )


app = create_app()
app.add_strategy(CrossSectionalMomentumBotVector)
app.add_market(
    market=MARKET, trading_symbol=TRADING_SYMBOL, initial_balance=1000,
)


if __name__ == "__main__":
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365)

    study = Study(
        name="cross-sectional-momentum-vector",
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
        strategy=CrossSectionalMomentumBotVector,
        study=study,
    )
    backtest = backtests[0]
    metrics = backtest.get_backtest_metrics(study_name=study.name)
    print(metrics)
