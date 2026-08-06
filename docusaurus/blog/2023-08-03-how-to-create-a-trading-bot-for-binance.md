---
slug: hot-to-create-a-trading-bot-for-binance
title: How to create a trading bot for binance
authors:
  name: Marc van Duyn
  title: How to create a trading bot for Binance
  url: https://github.com/mduyn
  image_url: https://github.com/mduyn.png
tags: [trading bot, binance, crypto, investing algorithm, investing algorithm framework]
---

Binance is one of the largest cryptocurrency exchanges, and the Investing Algorithm Framework can connect to it
out of the box through [CCXT](https://github.com/ccxt/ccxt). This post walks through connecting to Binance,
writing a simple strategy, backtesting it, and running it live.

## How to create a trading bot for Binance

```bash
pip install investing-algorithm-framework
```

## Connect to Binance

Binance requires an API key and secret for trading (unlike some exchanges, its public market data endpoints are
also easier to use reliably with a key). You can create a key pair in your
[Binance API Management](https://www.binance.com/en/my/settings/api-management) settings — a read-only key is
enough for backtesting, but live trading needs a key with trading permissions enabled.

Store the credentials in a `.env` file next to your bot. The framework picks them up automatically using the
`<MARKET>_API_KEY` / `<MARKET>_SECRET_KEY` naming convention:

```bash
# .env
BINANCE_API_KEY=<your_binance_api_key>
BINANCE_SECRET_KEY=<your_binance_secret_key>
```

```python
from dotenv import load_dotenv

from investing_algorithm_framework import create_app

load_dotenv()

app = create_app()
# Registers the portfolio AND reads BINANCE_API_KEY / BINANCE_SECRET_KEY from .env
app.add_market(market="binance", trading_symbol="USDT", initial_balance=1000)
```

> If you'd rather pass credentials explicitly (e.g. from a secrets manager) instead of a `.env` file, use
> `app.add_market_credential(MarketCredential(market="binance", api_key=..., secret_key=...))` — see
> [Portfolio Configuration](/docs/Getting%20Started/portfolio-configuration) in the docs.

## Create a strategy

Below is a simple RSI-based strategy: buy BTC when it's oversold, sell when it's overbought. It uses
[pyindicators](https://github.com/coding-kitties/PyIndicators) for the RSI calculation, and the framework's
built-in `PositionSize` to size the order — no manual bookkeeping required.

```bash
pip install pyindicators
```

```python
from typing import Any, Dict, Iterable

from pyindicators import rsi

from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize,
    Signal, SignalSide, signals_from_column,
)


class BinanceRSIStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC"]
    trading_symbol = "USDT"
    data_sources = [
        DataSource(
            identifier="BTC/USDT-ohlcv",
            data_type="OHLCV",
            market="binance",
            symbol="BTC/USDT",
            time_frame="4h",
            warmup_window=100,
        )
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20)
    ]

    def generate_signals(self, context, data: Dict[str, Any]) -> Iterable[Signal]:
        df = rsi(data["BTC/USDT-ohlcv"], source_column="Close", period=14, result_column="rsi")
        df["oversold"] = df["rsi"] < 30
        df["overbought"] = df["rsi"] > 70

        yield from signals_from_column(
            df, "oversold", side=SignalSide.OPEN_LONG, symbol="BTC", source="rsi_oversold"
        )
        yield from signals_from_column(
            df, "overbought", side=SignalSide.CLOSE_LONG, symbol="BTC", source="rsi_overbought"
        )
```

> **Want to add short selling?** RSI strategies are a natural fit for shorting, since overbought/oversold is
> symmetric: short when RSI is overbought (expecting a pullback) and cover when it dips back to oversold. Add two
> more lines to the same `generate_signals` method:
>
> ```python
>         yield from signals_from_column(
>             df, "overbought", side=SignalSide.OPEN_SHORT, symbol="BTC", source="rsi_overbought"
>         )
>         yield from signals_from_column(
>             df, "oversold", side=SignalSide.CLOSE_SHORT, symbol="BTC", source="rsi_oversold"
>         )
> ```
>
> The framework only ever holds one direction per symbol, so this doesn't double up with the long side — it
> just means the strategy takes a short instead of sitting in cash while BTC is overbought. Binance supports
> margin trading, but make sure the account/API key you're using has margin enabled before running this live.

```python
# app.py
from investing_algorithm_framework import create_app

from strategy import BinanceRSIStrategy

app = create_app()
app.add_strategy(BinanceRSIStrategy)
app.add_market(market="binance", trading_symbol="USDT", initial_balance=1000)
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

See [Backtesting](/docs/Getting%20Started/backtesting) for the full guide, including the much faster vector
backtesting mode for sweeping RSI thresholds and time frames before committing to a final set of parameters.

## Run your strategy

Once you're happy with the backtest results, running the same strategy live is just:

```python
if __name__ == "__main__":
    app.run()
```

The framework will trigger `generate_signals` on the schedule you defined (`TimeUnit.HOUR`, every 4 hours) and
place real orders on Binance through the credentials configured above. For running this unattended (rather than
on your own machine), see
[How to deploy a trading bot](/blog/how-to-deploy-a-trading-bot) for deploying it to AWS Lambda or Azure Functions.
