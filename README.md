<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)
<a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a> <br/>
[![GitHub stars](https://img.shields.io/github/stars/coding-kitties/investing-algorithm-framework.svg?style=social&label=Star&maxAge=1)](https://github.com/SeaQL/sea-orm/stargazers/) If you like what we do, consider starring, sharing and contributing!

# [Investing Algorithm Framework](https://github.com/coding-kitties/investing-algorithm-framework)

The Investing Algorithm Framework is a Python framework that enables swift and elegant development of trading bots.

## Sponsors

<a href="https://www.finterion.com/" target="_blank">
    <picture style="height: 30px;">
    <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
    <img src="static/sponsors/finterion-light.svg" alt="Finterion Logo" width="200px" height="50px">
    </picture>
</a>

## Features and planned features:

- [x] **Based on Python 3.9+**: Windows, macOS and Linux.
- [x] **Documentation**: [Documentation](https://investing-algorithm-framework.com)
- [x] **Persistence of portfolios, orders, positions and trades**: Persistence is achieved through sqlite.
- [x] **Limit orders**: Create limit orders for buying and selling.
- [x] **Trade models**: Models and functionality for trades, trades stop losses (fixed and trailing) and take profits (fixed and trailing).
- [x] **Market data sources**: Market data sources for OHLCV data and ticker data, and extendible with custom data and events.
- [x] **Polars and Pandas dataframes support** Out of the box dataframes support for fast data processing ([pola.rs](https://pola.rs/), [pandas](https://pandas.pydata.org/)).
- [x] **Azure Functions support**: Stateless running for cloud function deployments in Azure.
- [x] **Live trading**: Live trading.
- [x] **Backtesting and performance analysis reports** [example](./examples/backtest_example)
- [x] **Backtesting multiple algorithms with different backtest date ranges** [example](./examples/backtests_example)
- [x] **Backtest comparison and experiments**: Compare multiple backtests and run experiments.
- [x] **Order execution**: Currently support for a wide range of crypto exchanges through [ccxt](https://github.com/ccxt/ccxt) (Support for traditional asset brokers is planned).
- [x] **Web API**: Rest API for interacting with your deployed trading bot
- [x] **PyIndicators**: Works natively with [PyIndicators](https://github.com/coding-kitties/PyIndicators) for technical analysis on your Pandas and Polars dataframes.
- [ ] **Builtin WebUI (Planned)**: Builtin web UI to manage your bot and evaluate your backtests.
- [ ] **Manageable via Telegram (Planned)**: Manage the bot with Telegram.
- [ ] **Performance status report via Web UI and telegram(Planned)**: Provide a performance status of your current trades.
- [ ] **CI/CD integration (Planned)**: Tools for continuous integration and deployment (version tracking, comparison of backtests, automatic deployments).
- [ ] **Tracing and replaying of strategies in backtests (Planned)**: Tracing and replaying of strategies in backtests for specific dates and date ranges so you can evaluate your strategy step by step.
- [ ] **AWS Lambda support (Planned)**: Stateless running for cloud function deployments in AWS.
- [ ] **Azure App services support (Planned)**: deployments in Azure app services with Web UI.

## Example implementation

The following algorithm connects to binance and buys BTC every 2 hours.

```python
import logging.config
from dotenv import load_dotenv

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    TimeUnit, CCXTOHLCVMarketDataSource, Context, CCXTTickerMarketDataSource, \
    MarketCredential, DEFAULT_LOGGING_CONFIG, Algorithm, Context

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

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

# Bitvavo market credentials are read from .env file, or you can
# set them  manually as params
app.add_market_credential(MarketCredential(market="bitvavo"))
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo", trading_symbol="EUR", initial_balance=40
    )
)

algorithm = Algorithm(name="test_algorithm")

# Define a strategy for the algorithm that will run every 10 seconds
@algorithm.strategy(
    time_unit=TimeUnit.SECOND,
    interval=10,
    market_data_sources=[bitvavo_btc_eur_ticker, bitvavo_btc_eur_ohlcv_2h]
)
def perform_strategy(context: Context, market_data: dict):
    # Access the data sources with the indentifier
    polars_df = market_data["BTC-ohlcv"]
    ticker_data = market_data["BTC-ticker"]
    unallocated_balance = context.get_unallocated()
    positions = context.get_positions()
    trades = context.get_trades()
    open_trades = context.get_open_trades()
    closed_trades = context.get_closed_trades()

app.add_algorithm(algorithm)

if __name__ == "__main__":
    app.run()
```

> You can find more examples [here](./examples) folder.

## Backtesting and experiments

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

### Backtest experiments

The framework also supports backtest experiments. Backtest experiments allows you to
compare multiple algorithms and evaluate their performance. Ideally,
you would do this by parameterizing your strategy and creating a factory function that
creates the algorithm with the different parameters. You can find an example of this
in the [backtest experiments example](./examples/backtest_experiment).

## Broker/Exchange configuration

The framework has by default support for [ccxt](https://github.com/ccxt/ccxt).
This should allow you to connect to a lot of brokers/exchanges.

```python
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, create_app
app = create_app()
app.add_market_credential(
    MarketCredential(
        market="<your market>",
        api_key="<your api key>",
        secret_key="<your secret key>",
    )
)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your market>",
        initial_balance=400,
        trading_symbol="EUR"
    )
)
```

## Performance

We are continuously working on improving the performance of the framework. If
you have any suggestions, please let us know.

## How to install

You can download the framework with pypi.

```bash
pip install investing-algorithm-framework
```

## Installation for local development

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

## Disclaimer

If you use this framework for your investments, do not risk money
which you are afraid to lose, until you have clear understanding how
the framework works. We can't stress this enough:

BEFORE YOU START USING MONEY WITH THE FRAMEWORK, MAKE SURE THAT YOU TESTED
YOUR COMPONENTS THOROUGHLY. USE THE SOFTWARE AT YOUR OWN RISK.
THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR INVESTMENT RESULTS.

Also, make sure that you read the source code of any plugin you use or
implementation of an algorithm made with this framework.

## Documentation

All the documentation can be found online
at the [documentation webstie](https://investing-algorithm-framework.com)

In most cases, you'll probably never have to change code on this repo directly
if you are building your algorithm/bot. But if you do, check out the
contributing page at the website.

If you'd like to chat with investing-algorithm-framework users
and developers, [join us on Slack](https://inv-algo-framework.slack.com) or [join us on reddit](https://www.reddit.com/r/InvestingBots/)

## Acknowledgements

We want to thank all contributors to this project. A full list of all the people that contributed to the project can be
found [here](https://github.com/investing-algorithms/investing-algorithm-framework/blob/master/AUTHORS.md)

### [Bugs / Issues](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)

If you discover a bug in the framework, please [search our issue tracker](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)
first. If it hasn't been reported, please [create a new issue](https://github.com/investing-algorithms/investing-algorithm-framework/issues/new).

### Contributing

The investing algorithm framework is a community driven project.
We welcome you to participate, contribute and together help build the future trading bots developed in python.

Feel like the framework is missing a feature? We welcome your pull requests!
If you want to contribute to the project roadmap, please take a look at the [project board](https://github.com/coding-kitties/investing-algorithm-framework/projects?query=is%3Aopen).
You can pick up a task by assigning yourself to it.

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do*.
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `main`.
