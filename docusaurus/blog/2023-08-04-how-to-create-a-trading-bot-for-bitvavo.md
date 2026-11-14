---
slug: how-to-create-a-trading-bot-for-bitvavo
title: How to create a trading bot for bitvavo
authors:
    name: Marc van Duyn
    title: How to create a trading bot for bitvavo
    url: https://github.com/mduyn
    image_url: https://github.com/mduyn.png
tags: [trading bot, bitvavo, crypto, investing algorithm, investing algorithm framework]
---

[Bitvavo](https://bitvavo.com) is a European crypto exchange, and it's the exchange most of the framework's own
examples default to — partly because its market data (OHLCV, ticker) is public and doesn't require an API key,
which makes it convenient for backtesting and experimenting before you ever add real credentials.

## How to create a trading bot for bitvavo

```bash
pip install investing-algorithm-framework
```

## Connect to Bitvavo

For backtesting only, you don't need a Bitvavo account at all — market data is public:

```python
from investing_algorithm_framework import create_app

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=400)
```

To trade live, create an API key/secret pair in your Bitvavo account settings, and store them in a `.env` file.
The framework reads them automatically using the `BITVAVO_API_KEY` / `BITVAVO_SECRET_KEY` naming convention —
you don't need to change any code between backtesting and live trading:

```bash
# .env
BITVAVO_API_KEY=<your_bitvavo_api_key>
BITVAVO_SECRET_KEY=<your_bitvavo_secret_key>
```

```python
from dotenv import load_dotenv

load_dotenv()
```

## Create a strategy

Below is a simple EMA crossover strategy on BTC/EUR — buy when the fast EMA crosses above the slow EMA, sell on
the opposite crossover. It uses [pyindicators](https://github.com/coding-kitties/PyIndicators) for the moving
averages and a built-in take-profit rule to lock in gains automatically.

```bash
pip install pyindicators
```

```python
from typing import Any, Dict, Iterable

from pyindicators import ema, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize, TakeProfitRule,
    Signal, SignalSide, signals_from_column,
)


class BitvavoEMACrossoverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    trading_symbol = "EUR"
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type="OHLCV",
            market="bitvavo",
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=100,
        )
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25)
    ]
    # Take profit at +10%, trailing so it locks in further gains if price keeps rising
    take_profits = [
        TakeProfitRule(symbol="BTC", percentage_threshold=10, trailing=True, sell_percentage=100)
    ]

    def generate_signals(self, context, data: Dict[str, Any]) -> Iterable[Signal]:
        df = data["BTC/EUR-ohlcv"]
        df = ema(df, source_column="Close", period=9, result_column="fast")
        df = ema(df, source_column="Close", period=21, result_column="slow")
        df = crossover(df, first_column="fast", second_column="slow", result_column="cross_up")
        df = crossunder(df, first_column="fast", second_column="slow", result_column="cross_down")

        yield from signals_from_column(
            df, "cross_up", side=SignalSide.OPEN_LONG, symbol="BTC", source="ema_cross"
        )
        yield from signals_from_column(
            df, "cross_down", side=SignalSide.CLOSE_LONG, symbol="BTC", source="ema_cross"
        )
```

> **Want to add short selling?** The framework itself supports it — add an `OPEN_SHORT` signal on the same
> `cross_down` condition and a `CLOSE_SHORT` on `cross_up` to cover it:
>
> ```python
>         yield from signals_from_column(
>             df, "cross_down", side=SignalSide.OPEN_SHORT, symbol="BTC", source="ema_cross"
>         )
>         yield from signals_from_column(
>             df, "cross_up", side=SignalSide.CLOSE_SHORT, symbol="BTC", source="ema_cross"
>         )
> ```
>
> One Bitvavo-specific caveat, though: Bitvavo is a spot exchange, so there's no margin/short product to route a
> real `SHORT` order to there. This pattern works as-is for backtesting (useful to see whether shorting the
> drawdowns would even help), but to run it live you'd need to point `market` at an exchange that actually offers
> margin trading, like Binance — see
> [How to create a trading bot for Binance](/blog/hot-to-create-a-trading-bot-for-binance).

```python
# app.py
from investing_algorithm_framework import create_app

from strategy import BitvavoEMACrossoverStrategy

app = create_app()
app.add_strategy(BitvavoEMACrossoverStrategy)
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=400)
```

## Backtest your strategy

```python
# backtest.py
from datetime import datetime, timezone

from investing_algorithm_framework import BacktestDateRange, pretty_print_backtest

from app import app

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
)

if __name__ == "__main__":
    backtest = app.run_backtest(backtest_date_range=backtest_range)
    pretty_print_backtest(backtest)
```

Because Bitvavo's OHLCV data is public, you can iterate on this backtest — trying different EMA periods, time
frames, or take-profit thresholds — without ever touching an API key. See
[Backtesting](/docs/Getting%20Started/backtesting) for running many parameter combinations at once with vector
backtesting.

## Run your strategy

Once you're ready to go live, add your API credentials (see above) and run:

```python
if __name__ == "__main__":
    app.run()
```

The bot will now check BTC/EUR every 2 hours and place real limit orders on Bitvavo. See
[How to deploy a trading bot](/blog/how-to-deploy-a-trading-bot) if you want this running unattended in the cloud
instead of on your own machine.
