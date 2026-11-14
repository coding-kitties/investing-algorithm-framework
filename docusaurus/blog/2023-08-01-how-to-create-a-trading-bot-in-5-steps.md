---
slug: how-to-create-a-trading-bot-in-5-steps
authors:
    name: Marc van Duyn
    title: How to create a trading bot
    url: https://github.com/mduyn
    image_url: https://github.com/mduyn.png
tags: [trading bot, deployment, azure functions, aws lambda, crypto, investing algorithm, investing algorithm framework]
---

# How to build a trading bot in 5 steps
Would you like to build your own trading bot but do not know where to start? You have come to the right place.
In this guide we will walk you through the five steps of building a trading bot, and get you started with automated trading!

> The code is written in Python 3.10+ and the main framework used is the [Investing algorithm framework](https://investing-algorithm-framework.com) for building the trading bot.
> This post was updated to reflect the current version of the framework — see the [v9.0 release notes](/blog/v9-0-release) for what's new.

## 1 Choosing the right framework
There are a many libraries, packages and resources available to build a trading bot. To find the right
tools for you consider looking at the following list of [resources](https://wilsonfreitas.github.io/awesome-quant/).
For this blog we will use the [Investing algorithm framework](https://github.com/coding-kitties/investing-algorithm-framework).
This is a Python based framework that allows you to build your own trading bot. It is open-source and free to use.

## 2 Creating a trading bot with the investing algorithm framework
The investing algorithm framework has various options to build your own trading bot and implement a strategy.
Some key questions to consider when building your strategy are:

* How often should my bot run?
* Which market data should my bot use?
* Which indicators should my bot use?
* On which exchange or broker should my bot trade?
* How do I deploy my bot?

For our trading bot we would like to implement a simple strategy that buys and sells the cryptocurrency
bitcoin based on a set of simple indicators. The strategy will run every 2 hours. This means that every 2 hours the bot will
check the price of bitcoin and decide whether to buy or sell.

### 2.1 Setting up the trading bot

To set up the trading bot, we first need to install the investing algorithm framework. We'll also install
[pyindicators](https://github.com/coding-kitties/PyIndicators), a small library the framework's examples use for
technical indicators (moving averages, crossovers, ...).

```bash
pip install investing-algorithm-framework
pip install pyindicators
```

### 2.2 Specifying our market data
Next, we need to specify how often our trading bot runs and which market data it's going to use.
The investing algorithm framework supports various types of market data through `DataSource` objects. For this
example we will use the historical price data of bitcoin in candle stick format. In trading terms this is called
OHLCV (Open, High, Low, Close, Volume) data.

```python
from investing_algorithm_framework import DataSource

btc_eur_ohlcv = DataSource(
    identifier="BTC/EUR-ohlcv",
    data_type="OHLCV",
    market="BITVAVO",
    symbol="BTC/EUR",
    time_frame="2h",
    # Keep enough history for a 50-period moving average to warm up
    warmup_window=200,
)
```

### 2.3 Specifying our trading strategy
Now that we have set up the market data source for our trading bot, we can implement the trading strategy. For this
example we will implement a simple strategy that buys bitcoin when there is a golden cross between a fast and slow
moving average. The golden cross is a bullish signal that occurs when the short-term (fast) moving average crosses
above a long-term (slow) moving average.

For the sell signal we will use the opposite. We will sell bitcoin when there is a death cross between the fast and
the slow moving average. The death cross is a bearish signal that occurs when the short-term (fast) moving average
crosses below the long-term (slow) moving average.

So to summarize:
When the fast moving average crosses above the slow moving average, we buy. When the fast moving average crosses
below the slow moving average, we sell.

The recommended way to express this in the framework is a **signal-based strategy**: you implement
`generate_signals`, yielding `Signal` objects, and the framework takes care of turning those signals into orders
(including position sizing and risk rules — more on that below).

Create a new file called `strategy.py` and add the following code:

```python
from typing import Any, Dict, Iterable

from pyindicators import sma, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize,
    Signal, SignalSide, signals_from_column,
)


class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    trading_symbol = "EUR"
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type="OHLCV",
            market="BITVAVO",
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=200,
        )
    ]
    # Allocate 25% of the portfolio to a new BTC position
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25)
    ]

    def generate_signals(self, context, data: Dict[str, Any]) -> Iterable[Signal]:
        df = data["BTC/EUR-ohlcv"]
        df = sma(df, source_column="Close", period=9, result_column="fast")
        df = sma(df, source_column="Close", period=50, result_column="slow")
        df = crossover(df, first_column="fast", second_column="slow", result_column="golden_cross")
        df = crossunder(df, first_column="fast", second_column="slow", result_column="death_cross")

        yield from signals_from_column(
            df, "golden_cross", side=SignalSide.OPEN_LONG, symbol="BTC", source="golden_cross"
        )
        yield from signals_from_column(
            df, "death_cross", side=SignalSide.CLOSE_LONG, symbol="BTC", source="death_cross"
        )
```

That's the whole strategy. The framework calls `generate_signals` every 2 hours, and only opens a new BTC
position when there is no existing open order or position for it — you don't need to check
`has_open_orders`/`has_position` yourself, and you don't need to size the order by hand, the `position_sizes` rule
above (25% of the portfolio) takes care of that.

> If you need full manual control instead (custom order sizing, multiple conditions, exotic order types), the
> framework also supports overriding `run_strategy(self, context, data)` directly — see
> [Trading Strategies](/docs/Getting%20Started/strategies) in the docs for that lower-level approach.

### 2.4 Want this strategy to also go short?

So far the strategy only ever holds BTC or cash — it's **long-only**. Shorting means opening a position that
profits when the price *falls*: you sell borrowed BTC now and buy it back later, ideally at a lower price. The
framework supports this with two more `SignalSide` values, `OPEN_SHORT` and `CLOSE_SHORT`, which you can add to
the exact same `generate_signals` method:

```python
    def generate_signals(self, context, data: Dict[str, Any]) -> Iterable[Signal]:
        df = data["BTC/EUR-ohlcv"]
        df = sma(df, source_column="Close", period=9, result_column="fast")
        df = sma(df, source_column="Close", period=50, result_column="slow")
        df = crossover(df, first_column="fast", second_column="slow", result_column="golden_cross")
        df = crossunder(df, first_column="fast", second_column="slow", result_column="death_cross")

        # Long side: buy the golden cross, sell (exit) the death cross
        yield from signals_from_column(
            df, "golden_cross", side=SignalSide.OPEN_LONG, symbol="BTC", source="golden_cross"
        )
        yield from signals_from_column(
            df, "death_cross", side=SignalSide.CLOSE_LONG, symbol="BTC", source="death_cross"
        )
        # Short side: mirror the same crossovers onto OPEN_SHORT / CLOSE_SHORT
        yield from signals_from_column(
            df, "death_cross", side=SignalSide.OPEN_SHORT, symbol="BTC", source="death_cross"
        )
        yield from signals_from_column(
            df, "golden_cross", side=SignalSide.CLOSE_SHORT, symbol="BTC", source="golden_cross"
        )
```

The framework only ever keeps one open direction per symbol at a time (long *or* short, never both), so the new
`OPEN_SHORT` signal on a death cross is only actually placed once any existing long has already been closed —
you don't need to guard against holding both. Before enabling this live, double-check that your broker or
exchange actually offers margin/short-selling on the symbol you're trading; plenty of spot-only exchanges don't.

## 3 Testing our trading strategy
Now that we have implemented our trading strategy we can test it. To test our strategy we will use the
backtesting functionality of the investing algorithm framework. This allows us to test our strategy on historical data.

Create a new file called `app.py` that wires up the app, and a `backtest.py` that runs it over a date range:

```python
# app.py
from investing_algorithm_framework import create_app

from strategy import GoldenCrossDeathCrossTradingStrategy

app = create_app()
app.add_strategy(GoldenCrossDeathCrossTradingStrategy)
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=400)
```

```python
# backtest.py
from datetime import datetime, timezone

from investing_algorithm_framework import BacktestDateRange, pretty_print_backtest

from app import app

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2023, 12, 30, tzinfo=timezone.utc),
)

if __name__ == "__main__":
    backtest = app.run_backtest(backtest_date_range=backtest_range)
    pretty_print_backtest(backtest)
```

Running `python backtest.py` prints a report to the console with the backtest window, the number of orders and
trades, and the resulting portfolio performance — the key numbers to look at are the final balance, total net
gain and the percentage of winning trades:

```bash
$ python backtest.py
====================Backtest report===============================
Start date: 2023-01-01 00:00:00
End date: 2023-12-30 00:00:00
Number of days: 363
Number of runs: 4357
====================Portfolio overview============================
Number of orders: 128
Initial balance: 400.0000 EUR
Final balance: 468.1028 EUR
Total net gain: 68.1028 EUR (17.0257%)
====================Trades overview================================
Number of trades closed: 64
Percentage of positive trades: 29.6875%
Average trade size: 108.4551 EUR
Average trade duration: 77.1 hours
```

As you can see this trading strategy is profitable with a growth rate of 17% on its closed trades.
When creating a trading strategy it's also very important to run the strategy on a time range that was considered
to be a market downturn for your selected assets. This will help you determine if your trading strategy is robust
enough to handle market downturns.

For bitcoin, the period from 2021-11-11 to 2022-11-11 was considered to be a market downturn. Change the
`backtest_range` above to that period and re-run it, and you'll see something like this:

```bash
$ python backtest.py
====================Backtest report===============================
Start date: 2021-11-11 00:00:00
End date: 2022-11-11 00:00:00
Number of days: 365
Number of runs: 4381
====================Portfolio overview============================
Number of orders: 130
Initial balance: 400.0000 EUR
Final balance: 356.0855 EUR
Total net gain: -43.9145 EUR (-10.9786%)
====================Trades overview================================
Number of trades closed: 65
Percentage of positive trades: 29.2308%
Average trade size: 89.5404 EUR
Average trade duration: 60.0 hours
```

As you can see this trading strategy is not profitable, with a loss of about -11% on its closed trades over that
period. We will try to improve it in the next section. The important thing to note here is that our trading
strategy is not robust enough to handle market downturns.

> You can also explore a backtest interactively instead of reading console output — see
> [Backtest Reports](/docs/Getting%20Started/backtest-reports) for `BacktestReport(backtest).show()`, which opens
> an interactive dashboard with the equity curve, trades and metrics.

## 4 Improving our trading strategy
In the previous section we saw that our trading bot was not profitable during a market downturn. In this section
we will try to improve our trading strategy. Whenever creating a trading bot you should always experiment with
different metrics and parameters. We'll make the following changes:

- Add a stop loss to our open positions, so we pre-emptively close a trade when the price drops too far from its peak.
- Add a trend filter, so we only sell when the price is below a longer-term trend line.
- Change our fast moving average from a simple moving average (SMA) to an exponential moving average (EMA), which gives more weight to the most recent prices.

Both the stop loss and the trend filter are a few lines of configuration rather than hand-rolled logic, because
the framework has built-in risk rules:

```python
from typing import Any, Dict, Iterable

import pandas as pd
from pyindicators import ema, sma, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize, StopLossRule,
    Signal, SignalSide, signals_from_column,
)


class ImprovedGoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    trading_symbol = "EUR"
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type="OHLCV",
            market="BITVAVO",
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=200,
        )
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25)
    ]
    # Trailing 6% stop loss: sell if price drops 6% from its peak since entry
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=6, trailing=True, sell_percentage=100
        )
    ]

    def _with_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = ema(df, source_column="Close", period=9, result_column="fast")
        df = sma(df, source_column="Close", period=50, result_column="slow")
        df = sma(df, source_column="Close", period=100, result_column="trend")
        return df

    def generate_signals(self, context, data: Dict[str, Any]) -> Iterable[Signal]:
        df = self._with_indicators(data["BTC/EUR-ohlcv"])
        df = crossover(df, first_column="fast", second_column="slow", result_column="golden_cross")
        # Only sell on a crossunder against the trend line, not the fast/slow pair
        df = crossunder(df, first_column="fast", second_column="trend", result_column="trend_break")

        yield from signals_from_column(
            df, "golden_cross", side=SignalSide.OPEN_LONG, symbol="BTC", source="golden_cross"
        )
        yield from signals_from_column(
            df, "trend_break", side=SignalSide.CLOSE_LONG, symbol="BTC", source="trend_break"
        )
```

> Want this version to short as well? Add the same `OPEN_SHORT` / `CLOSE_SHORT` pair shown in
> [step 2.4](#24-want-this-strategy-to-also-go-short) above, mirrored onto `trend_break` / `golden_cross`. A
> `stop_losses` rule defined with `symbol="BTC"` protects both directions — the framework tracks the stop
> relative to whichever side (long or short) is currently open.

Note what disappeared compared to the first version: there is no more manual `has_open_orders`/`has_position`
bookkeeping, no manual order sizing, and no manual loop that checks every open trade's price against a stop-loss
percentage — the `stop_losses` rule is evaluated by the framework on every tick, in both backtests and live
trading.

Re-running the downturn backtest (2021-11-11 to 2022-11-11) with this improved strategy gives a noticeably
smaller drawdown:

```bash
$ python backtest.py
====================Backtest report===============================
Start date: 2021-11-11 00:00:00
End date: 2022-11-11 00:00:00
Number of days: 365
Number of runs: 4381
====================Portfolio overview============================
Number of orders: 34
Initial balance: 400.0000 EUR
Final balance: 378.3081 EUR
Total net gain: -21.6919 EUR (-5.4230%)
====================Trades overview================================
Number of trades closed: 17
Percentage of positive trades: 11.7647%
Average trade size: 95.9035 EUR
Average trade duration: 69.3 hours
```

And for the favorable period (2023-01-01 to 2023-12-30):

```bash
$ python backtest.py
====================Backtest report===============================
Start date: 2023-01-01 00:00:00
End date: 2023-12-30 00:00:00
Number of days: 363
Number of runs: 4357
====================Portfolio overview============================
Number of orders: 90
Initial balance: 400.0000 EUR
Final balance: 464.3659 EUR
Total net gain: 64.3659 EUR (16.0915%)
====================Trades overview================================
Number of trades closed: 45
Percentage of positive trades: 31.1111%
Average trade size: 109.6916 EUR
Average trade duration: 123.3 hours
```

The drawdown during the bear market shrank from about -11% to about -5%, at the cost of giving up a little of the
upside during the bull market (17.0% → 16.1%). That trade-off — smaller losses in bad conditions, slightly smaller
gains in good ones — is typical of adding risk controls, and it's exactly the kind of comparison backtesting each
version of your strategy lets you make before risking real money.


## 5 Deploying our trading bot
To deploy our trading bot we'll run it as an Azure Function on a timer, so it wakes up and checks the market
every 2 hours. The framework ships a CLI (`iaf`) that scaffolds and deploys this for you — no hand-written
`host.json`, `function_app.py`, or Azure resource scripts needed.

Before we start, make sure you have:

- A Microsoft Azure account. You can create a free account [here](https://azure.microsoft.com/en-us/free/).
- The Azure CLI installed and logged in (`az login`). Installation instructions [here](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli).
- The Azure Functions Core Tools installed: `npm install -g azure-functions-core-tools@4`.

### 5.1 Scaffold an Azure Function project

```bash
iaf init --type azure_function --path ./my-trading-bot
cd my-trading-bot
```

This generates `function_app.py` (the Azure Function entry point wired up to call your strategy on a timer),
`host.json`, `local.settings.json`, a `requirements.txt` with the Azure SDK dependencies, and an `.env.example`.
Copy your strategy code from the earlier steps into the generated `strategies/` package, and add your Bitvavo API
credentials to a `.env` file:

```bash
# .env
BITVAVO_API_KEY=<your_bitvavo_api_key>
BITVAVO_SECRET_KEY=<your_bitvavo_secret_key>
```

### 5.2 Deploy it

```bash
iaf deploy-azure-function \
  --resource_group trading-bots-rg \
  --deployment_name btc-trader \
  --region westeurope \
  --create_resource_group_if_not_exists
```

This single command creates the resource group (if it doesn't already exist), sets up a storage account and blob
container for state persistence, reads your `.env` file and applies it as Function App configuration, and deploys
the Function App using the Azure Functions Core Tools.

If everything went well, you should see the resource group, storage account and function app in your Azure portal,
and the trading bot running on its schedule.

> Prefer AWS? The same CLI has an equivalent one-liner: `iaf init --type aws_lambda` to scaffold, then
> `iaf deploy-aws-lambda --lambda_function_name my-trading-bot --region eu-west-1` to deploy — see
> [Deployment](/docs/Getting%20Started/deployment) in the docs for the full reference, including how to pass
> exchange credentials as Lambda environment variables.

## 6 Conclusion
In this tutorial we have shown you how to build a trading bot with the investing algorithm framework.
We have also shown you how to test your trading bot and how to make some small improvements to let your trading bot perform better.
Finally, we have shown you how to deploy your trading bot to Azure.

I hope you have enjoyed this tutorial and that you have learned something new. Please let me know if you have any questions or feedback. If
you would like to learn more about the investing algorithm framework you can check out the [documentation](https://investing-algorithm-framework.com/), and
the [tutorial notebooks](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/tutorial) in the repository for a
more in-depth, notebook-driven walkthrough of the same workflow.

Also, don't forget to star the [investing algorithm framework](https://github.com/coding-kitties/investing-algorithm-framework) on github if you like it!

You can follow me on [twitter](https://twitter.com/mduyn) or connect with me on [linkedin](https://twitter.com/marcvanduyn). Also if you
would like to read upcoming blogs you can subscribe to my [medium account](https://medium.com/@marcvanduyn).
