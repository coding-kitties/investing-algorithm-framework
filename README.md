<div align="center"> <h1><a href="https://coding-kitties.github.io/investing-algorithm-framework/" target="_blank">Investing Algorithm Framework</a></h1> <p><b>Rapidly build, backtest, and deploy quantitative strategies and trading bots</b></p> <a target="_blank" href="https://coding-kitties.github.io/investing-algorithm-framework/">📖 View Documentation</a> | <a href="https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation">🚀 Getting Started</a> </div>

---

<div align="center"> <a href="https://coding-kitties.github.io/investing-algorithm-framework/">
<a target="_blank" href="https://discord.gg/dQsRmGZP"><img src="https://img.shields.io/discord/1345358169777635410.svg?color=7289da&label=TradeBotLab%20Discord&logo=discord&style=flat"></a>
<img src="https://img.shields.io/badge/docs-website-brightgreen"></a> <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml"><img src="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml/badge.svg"></a> <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml"><img src="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg"></a> <a href="https://pepy.tech/project/investing-algorithm-framework"><img src="https://pepy.tech/badge/investing-algorithm-framework"></a> <a href="https://pypi.org/project/investing-algorithm-framework/"><img src="https://img.shields.io/pypi/v/investing-algorithm-framework.svg"></a> <a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a> <a href="https://github.com/coding-kitties/investing-algorithm-framework/stargazers"><img src="https://img.shields.io/github/stars/coding-kitties/investing-algorithm-framework.svg?style=social&label=Star"></a>
 </div>

> If you like what we do, consider starring, sharing and contributing!

<div align="center">
<img src="static/showcase.svg" alt="Investing Algorithm Framework Logo" style="height: 50vh; max-height: 750px;">
</div>

The investing algorithm framework is a Python framework designed to help you build, backtest, and deploy quantitative trading strategies. It comes with a event-based backtesting engine, ensuring an accurate and realistic evaluation of your strategies. The framework supports live trading with multiple exchanges and has various deployment options including Azure Functions and AWS Lambda.
The framework is designed to be extensible, allowing you to add custom strategies, data providers, and order executors. It also supports multiple data sources, including OHLCV, ticker, and custom data, with integration for both Polars and Pandas.

## Sponsors

<a href="https://www.finterion.com/" target="_blank">
    <picture style="height: 30px;">
    <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
    <img src="static/sponsors/finterion-light.png" alt="Finterion Logo" width="200px" height="50px">
    </picture>
</a>


## 🌟 Features

- [x] Python 3.10+: Cross-platform support for Windows, macOS, and Linux.
- [x] Backtesting: Simulate strategies with detailed performance reports.
- [x] Live Trading: Execute trades in real-time with support for multiple exchanges via ccxt.
- [x] Portfolio Management: Manage portfolios, trades, and positions with persistence via SQLite.
- [x] Market Data Sources: Fetch OHLCV, ticker, and custom data with support for Polars and Pandas.
- [x] Azure Functions Support: Deploy stateless trading bots to Azure.
- [x] Web API: Interact with your bot via REST API.
- [x] PyIndicators Integration: Perform technical analysis directly on your dataframes.
- [x] Extensibility: Add custom strategies, data providers, order executors so you can connect your trading bot to your favorite exchange or broker.

## 🚀 Quickstart

Installation
Install the framework via [PyPI](https://pypi.org/project/investing-algorithm-framework/):

1. First install the framework using `pip`. The Investing Algorithm Framework is hosted on [PyPi].

```bash
pip install investing-algorithm-framework
```

Run the following command to set up your project:

```bash
investing-algorithm-framewor init
```

For a web-enabled version:

```bash
investing-algorithm-framework init --web
```

This will create:

* app.py: The entry point for your bot.
* strategy.py: A sample strategy file to get started.

> Note: Keep the app.py file as is. You can modify strategy.py and add additional files to build your bot.
> You can always change the app to the web version by changing the `app.py` file.

---

## 📈 Example: A Simple Trading Bot
The following example trading bot implements a simple moving average strategy.
The strategy will use data from bitvavo exchange and will calculate 
the 20, 50 and 100 period exponential moving averages (EMA) and the 
14 period relative strength index (RSI).

> This example uses [PyIndicators](https://github.com/coding-kitties/pyindicators) for technical analysis.
> This dependency is not part of the framework, but is used to perform technical analysis on the dataframes.
> You can install it using pip: pip install pyindicators.

```python
import logging.config
from dotenv import load_dotenv

from pyindicators import ema, rsi

from investing_algorithm_framework import create_app, TimeUnit, Context, BacktestDateRange, \
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, DEFAULT_LOGGING_CONFIG, \
    TradingStrategy, SnapshotInterval, convert_polars_to_pandas, BacktestReport

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# OHLCV data for candles
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)
# Ticker data for orders, trades and positions
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

app = create_app()
# Registered bitvavo market, credentials are read from .env file by default
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=100)

class MyStrategy(TradingStrategy):
    interval = 2
    time_unit = TimeUnit.HOUR
    data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def run_strategy(self, context: Context, market_data):

        if context.has_open_orders(target_symbol="BTC"):
            logger.info("There are open orders, skipping strategy iteration.")
            return

        print(market_data)

        data = convert_polars_to_pandas(market_data["BTC-ohlcv"])
        data = ema(data, source_column="Close", period=20, result_column="ema_20")
        data = ema(data, source_column="Close", period=50, result_column="ema_50")
        data = ema(data, source_column="Close", period=100, result_column="ema_100")
        data = rsi(data, source_column="Close", period=14, result_column="rsi_14")

        if context.has_position("BTC") and self.sell_signal(data):
            context.create_limit_sell_order(
                "BTC", percentage_of_position=100, price=data["Close"].iloc[-1]
            )
            return

        if not context.has_position("BTC") and self.buy_signal(data):
            context.create_limit_buy_order(
                "BTC", percentage_of_portfolio=20, price=data["Close"].iloc[-1]
            )
            return

    def buy_signal(self, data):
        if len(data) < 100:
            return False
        last_row = data.iloc[-1]
        if last_row["ema_20"] > last_row["ema_50"] and last_row["ema_50"] > last_row["ema_100"]:
            return True
        return False

    def sell_signal(self, data):

        if data["ema_20"].iloc[-1] < data["ema_50"].iloc[-1] and \
           data["ema_20"].iloc[-2] >= data["ema_50"].iloc[-2]:
            return True

        return False

date_range = BacktestDateRange(
    start_date="2023-08-24 00:00:00", end_date="2023-12-02 00:00:00"
)
app.add_strategy(MyStrategy)

if __name__ == "__main__":
    # Run the backtest with a daily snapshot interval for end-of-day granular reporting
    backtest = app.run_backtest(
        backtest_date_range=date_range, initial_amount=100, snapshot_interval=SnapshotInterval.STRATEGY_ITERATION
    )
    backtest_report = BacktestReport(backtests=[backtest])
    backtest_report.show()
```

> You can find more examples [here](./examples) folder.

## 🔍 Backtesting

The framework also supports backtesting and performing backtest experiments. After a backtest, you can print a report that shows the performance of your trading bot.

To run a single backtest you can use the example code that can be found [here](./examples/backtest_example). Simply run:

> Its assumed here that you have cloned the repository, installed the framework and
> are in the root of the project.

```bash
python examples/backtest_example/run_backtest.py
```

### Backtesting report

You can use the ```pretty_print_backtest``` function to print a backtest report.
For example if you run the [moving average example trading bot](./examples/backtest_example/run_backtest.py)
you will get the following backtesting report:

```bash
                  :%%%#+-          .=*#%%%        Backtest report
                  *%%%%%%%+------=*%%%%%%%-       ---------------------------
                  *%%%%%%%%%%%%%%%%%%%%%%%-       Start date: 2023-08-24 00:00:00
                  .%%%%%%%%%%%%%%%%%%%%%%#        End date: 2023-12-02 00:00:00
                   #%%%####%%%%%%%%**#%%%+        Number of days: 100
             .:-+*%%%%- -+..#%%%+.+-  +%%%#*=-:   Number of runs: 1201
              .:-=*%%%%. += .%%#  -+.-%%%%=-:..   Number of orders: 15
              .:=+#%%%%%*###%%%%#*+#%%%%%%*+-:    Initial balance: 400.0
                    +%%%%%%%%%%%%%%%%%%%=         Final balance: 453.07
                :++  .=#%%%%%%%%%%%%%*-           Total net gain: 18.85 4.7%
               :++:      :+%%%%%%#-.              Growth: 53.07 13.27%
              :++:        .%%%%%#=                Number of trades closed: 2
             :++:        .#%%%%%#*=               Number of trades open(end of backtest): 2
            :++-        :%%%%%%%%%+=              Percentage positive trades: 75.0%
           .++-        -%%%%%%%%%%%+=             Percentage negative trades: 25.0%
          .++-        .%%%%%%%%%%%%%+=            Average trade size: 98.79 EUR
         .++-         *%%%%%%%%%%%%%*+:           Average trade duration: 189.0 hours
        .++-          %%%%%%%%%%%%%%#+=
        =++........:::%%%%%%%%%%%%%%*+-
        .=++++++++++**#%%%%%%%%%%%%%++.

Positions overview
╭────────────┬──────────┬──────────────────────┬───────────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending buy amount │   Pending sell amount │   Cost (EUR) │ Value (EUR)   │ Percentage of portfolio   │ Growth (EUR)   │ Growth_rate   │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │ 253.09   │                    0 │                     0 │       253.09 │ 253.09 EUR    │ 55.86%                    │ 0.00 EUR       │ 0.00%         │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ BTC        │   0.0028 │                    0 │                     0 │        97.34 │ 99.80 EUR     │ 22.03%                    │ 2.46 EUR       │ 2.52%         │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ DOT        │  19.9521 │                    0 │                     0 │       100    │ 100.18 EUR    │ 22.11%                    │ 0.18 EUR       │ 0.18%         │
╰────────────┴──────────┴──────────────────────┴───────────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
Trades overview
╭───────────────────┬────────────────┬───────────────────────┬───────────────────────────┬──────────────────┬──────────────────┬─────────────┬────────────────────┬──────────────────────────────┬─────────────────────────────────╮
│ Pair (Trade id)   │ Status         │ Amount (remaining)    │ Net gain (EUR)            │ Open date        │ Close date       │ Duration    │   Open price (EUR) │ Close price's (EUR)          │ High water mark                 │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ BTC/EUR (1)       │ CLOSED         │ 0.0040 (0.0000) BTC   │ 1.98 (2.02%)              │ 2023-09-13 14:00 │ 2023-09-22 12:00 │ 214.0 hours │           24490.4  │ 24984.93                     │ 25703.77 EUR (2023-09-19 14:00) │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ DOT/EUR (2)       │ CLOSED, SL, TP │ 24.7463 (0.0000) DOT  │ 13.53 (13.53%)            │ 2023-10-30 04:00 │ 2023-11-15 02:00 │ 382.0 hours │               4.04 │ 4.23, 4.38, 4.24, 4.25, 4.79 │ 5.45 EUR (2023-11-12 10:00)     │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ BTC/EUR (3)       │ CLOSED         │ 0.0030 (0.0000) BTC   │ -0.20 (-0.20%)            │ 2023-11-06 14:00 │ 2023-11-06 16:00 │ 2.0 hours   │           32691.5  │ 32625.87                     │ 32625.87 EUR (2023-11-06 16:00) │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ BTC/EUR (4)       │ CLOSED, TP     │ 0.0030 (0.0000) BTC   │ 3.54 (3.56%)              │ 2023-11-07 22:00 │ 2023-11-14 12:00 │ 158.0 hours │           33126.6  │ 34746.64, 33865.42           │ 34967.12 EUR (2023-11-10 22:00) │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ BTC/EUR (5)       │ OPEN           │ 0.0028 (0.0028) BTC   │ 2.46 (2.52%) (unrealized) │ 2023-11-29 12:00 │                  │ 60.0 hours  │           34765.9  │                              │ 35679.63 EUR (2023-12-01 16:00) │
├───────────────────┼────────────────┼───────────────────────┼───────────────────────────┼──────────────────┼──────────────────┼─────────────┼────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ DOT/EUR (6)       │ OPEN           │ 19.9521 (19.9521) DOT │ 0.18 (0.18%) (unrealized) │ 2023-11-30 18:00 │                  │ 30.0 hours  │               5.01 │                              │ 5.05 EUR (2023-11-30 20:00)     │
╰───────────────────┴────────────────┴───────────────────────┴───────────────────────────┴──────────────────┴──────────────────┴─────────────┴────────────────────┴──────────────────────────────┴─────────────────────────────────╯
Stop losses overview
╭────────────────────┬───────────────┬──────────┬──────────┬─────────────────────────────────┬──────────────┬────────────────┬───────────────────────────────┬──────────────┬───────────┬───────────────╮
│ Trade (Trade id)   │ Status        │ Active   │ Type     │ Stop Loss (Initial Stop Loss)   │ Open price   │ Sell price's   │ High water mark               │ Percentage   │ Size      │ Sold amount   │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ BTC/EUR (1)        │ NOT TRIGGERED │ False    │ TRAILING │ 24418.58 (23265.85) (5.0)% EUR  │ 24490.37 EUR │ None           │ 25703.77 EUR 2023-09-19 14:00 │ 50.0%        │ 0.00 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ DOT/EUR (2)        │ TRIGGERED     │ False    │ TRAILING │ 4.28 (3.84) (5.0)% EUR          │ 4.04 EUR     │ 4.239,4.254    │ 4.51 EUR 2023-11-01 20:00     │ 50.0%        │ 12.37 DOT │ 12.3732 DOT   │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ BTC/EUR (3)        │ NOT TRIGGERED │ False    │ TRAILING │ 31056.93 (31056.93) (5.0)% EUR  │ 32691.51 EUR │ None           │ 32691.51 EUR                  │ 50.0%        │ 0.00 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ BTC/EUR (4)        │ NOT TRIGGERED │ False    │ TRAILING │ 33218.76 (31470.27) (5.0)% EUR  │ 33126.60 EUR │ None           │ 34967.12 EUR 2023-11-10 22:00 │ 50.0%        │ 0.00 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ BTC/EUR (5)        │ NOT TRIGGERED │ True     │ TRAILING │ 33895.65 (33027.62) (5.0)% EUR  │ 34765.92 EUR │ None           │ 35679.63 EUR 2023-12-01 16:00 │ 50.0%        │ 0.00 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────┼──────────────┼────────────────┼───────────────────────────────┼──────────────┼───────────┼───────────────┤
│ DOT/EUR (6)        │ NOT TRIGGERED │ True     │ TRAILING │ 4.80 (4.76) (5.0)% EUR          │ 5.01 EUR     │ None           │ 5.05 EUR 2023-11-30 20:00     │ 50.0%        │ 9.98 DOT  │               │
╰────────────────────┴───────────────┴──────────┴──────────┴─────────────────────────────────┴──────────────┴────────────────┴───────────────────────────────┴──────────────┴───────────┴───────────────╯
Take profits overview
╭────────────────────┬───────────────┬──────────┬──────────┬─────────────────────────────────────┬──────────────┬────────────────┬─────────────────────────────────┬──────────────┬─────────────┬───────────────╮
│ Trade (Trade id)   │ Status        │ Active   │ Type     │ Take profit (Initial Take Profit)   │ Open price   │ Sell price's   │ High water mark                 │ Percentage   │ Size        │ Sold amount   │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (1)        │ NOT TRIGGERED │ False    │ TRAILING │ 25714.89 (25714.89) (5.0)% EUR      │ 24490.37 EUR │ None           │                                 │ 50.0%        │ 0.0020 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (1)        │ NOT TRIGGERED │ False    │ TRAILING │ 26939.41 (26939.41) (10.0)% EUR     │ 24490.37 EUR │ None           │                                 │ 20.0%        │ 0.0008 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ DOT/EUR (2)        │ TRIGGERED     │ False    │ TRAILING │ 4.24 (4.24) (5.0)% EUR              │ 4.04 EUR     │ 4.233          │ 4.30 EUR (2023-10-31 00:00)     │ 50.0%        │ 12.3732 DOT │ 12.3732 DOT   │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ DOT/EUR (2)        │ TRIGGERED     │ False    │ TRAILING │ 4.45 (4.45) (10.0)% EUR             │ 4.04 EUR     │ 4.377          │ 4.51 EUR (2023-11-01 20:00)     │ 20.0%        │ 4.9493 DOT  │ 4.9493 DOT    │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (3)        │ NOT TRIGGERED │ False    │ TRAILING │ 34326.09 (34326.09) (5.0)% EUR      │ 32691.51 EUR │ None           │                                 │ 50.0%        │ 0.0015 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (3)        │ NOT TRIGGERED │ False    │ TRAILING │ 35960.66 (35960.66) (10.0)% EUR     │ 32691.51 EUR │ None           │                                 │ 20.0%        │ 0.0006 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (4)        │ TRIGGERED     │ False    │ TRAILING │ 34782.93 (34782.93) (5.0)% EUR      │ 33126.60 EUR │ 34746.64       │ 34967.12 EUR (2023-11-10 22:00) │ 50.0%        │ 0.0015 BTC  │ 0.0015 BTC    │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (4)        │ NOT TRIGGERED │ False    │ TRAILING │ 36439.26 (36439.26) (10.0)% EUR     │ 33126.60 EUR │ None           │                                 │ 20.0%        │ 0.0006 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (5)        │ NOT TRIGGERED │ True     │ TRAILING │ 36504.22 (36504.22) (5.0)% EUR      │ 34765.92 EUR │ None           │                                 │ 50.0%        │ 0.0014 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ BTC/EUR (5)        │ NOT TRIGGERED │ True     │ TRAILING │ 38242.51 (38242.51) (10.0)% EUR     │ 34765.92 EUR │ None           │                                 │ 20.0%        │ 0.0006 BTC  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ DOT/EUR (6)        │ NOT TRIGGERED │ True     │ TRAILING │ 5.26 (5.26) (5.0)% EUR              │ 5.01 EUR     │ None           │                                 │ 50.0%        │ 9.9761 DOT  │               │
├────────────────────┼───────────────┼──────────┼──────────┼─────────────────────────────────────┼──────────────┼────────────────┼─────────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ DOT/EUR (6)        │ NOT TRIGGERED │ True     │ TRAILING │ 5.51 (5.51) (10.0)% EUR             │ 5.01 EUR     │ None           │                                 │ 20.0%        │ 3.9904 DOT  │               │
╰────────────────────┴───────────────┴──────────┴──────────┴─────────────────────────────────────┴──────────────┴────────────────┴─────────────────────────────────┴──────────────┴─────────────┴───────────────╯
```

## 🌐 Deployment to Azure

Prerequisites

Ensure Azure Functions Core Tools are installed:

```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```
Deploying to Azure
Use the provided deployment script:

This script:

```
investing-algorithm-framework deploy
```

This script:

* Creates Azure resources (e.g., storage accounts, function apps).
* Sets environment variables for the Azure Function.
* Deploys your bot to Azure.

## 📚 Documentation
Comprehensive documentation is available at [github pages](https://coding-kitties.github.io/investing-algorithm-framework/).

## 🛠️ Development

Local Development

Clone the repository and install dependencies using Poetry:

The framework is built with poetry. To install the framework for local development, you can run the following commands:

> Make sure you have poetry installed. If you don't have poetry installed, you can find installation instructions [here](https://python-poetry.org/docs/#installation)

```bash
git clone http
cd investing-algorithm-framework
poetry install
```

### Running tests

To run the tests, you can run the following command:

```bash
# In the root of the project
python -m unittest discover -s tests
```

## ⚠️ Disclaimer

If you use this framework for your investments, do not risk money
which you are afraid to lose, until you have clear understanding how the framework works. We can't stress this enough:

BEFORE YOU START USING MONEY WITH THE FRAMEWORK, MAKE SURE THAT YOU TESTED
YOUR COMPONENTS THOROUGHLY. USE THE SOFTWARE AT YOUR OWN RISK.
THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR INVESTMENT RESULTS.

Also, make sure that you read the source code of any plugin you use or
implementation of an algorithm made with this framework.

We welcome contributions! Check out the project board and issues to get started.

## Documentation

All the documentation can be found online
at the [documentation webstie](https://coding-kitties.github.io/investing-algorithm-framework/)

In most cases, you'll probably never have to change code on this repo directly
if you are building your algorithm/bot. But if you do, check out the
contributing page at the website.

If you'd like to chat with investing-algorithm-framework users
and developers, [join us on Slack](https://inv-algo-framework.slack.com) or [join us on reddit](https://www.reddit.com/r/InvestingBots/)

## 🤝 Contributing

The investing algorithm framework is a community driven project.
We welcome you to participate, contribute and together help build the future trading bots developed in python.

To get started, please read the [contributing guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing&20Guide/contributing).

Feel like the framework is missing a feature? We welcome your pull requests!
If you want to contribute to the project roadmap, please take a look at the [project board](https://github.com/coding-kitties/investing-algorithm-framework/projects?query=is%3Aopen).
You can pick up a task by assigning yourself to it.

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do*.
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `main`.

## 📬 Support

* [Reddit Community](https://www.reddit.com/r/InvestingBots/)
* [Discord Community](https://discord.gg/dQsRmGZP")


## 🏆 Acknowledgements

We want to thank all contributors to this project. A full list of all the people that contributed to the project can be
found [here](https://github.com/investing-algorithms/investing-algorithm-framework/blob/master/AUTHORS.md)

### [Bugs / Issues](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)

If you discover a bug in the framework, please [search our issue tracker](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)
first. If it hasn't been reported, please [create a new issue](https://github.com/investing-algorithms/investing-algorithm-framework/issues/new).
