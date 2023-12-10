<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)
<a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a>
###### Sponsors
<p align="left">
<a href="https://finterion.com">
  <img alt="Finterion" src="https://logicfunds-web-app-images.s3.eu-central-1.amazonaws.com/finterion.png" width="200px" />
</a>
</p>


# [Investing Algorithm Framework](https://github.com/coding-kitties/investing-algorithm-framework)

The Investing Algorithm Framework is a Python tool that enables swift and 
elegant development of investment algorithms and trading bots. It comes with all the necessary 
components for creating algorithms, including data provisioning, portfolio management, and order execution.


## Example implementation
The following algorithm connects to binance and buys BTC every 5 seconds. 
It also exposes an REST API that allows you to interact with the algorithm.
```python
import pathlib
from datetime import datetime, timedelta
from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, CCXTOHLCVMarketDataSource, Algorithm, \
    CCXTTickerMarketDataSource

# Define market data sources
# OHLCV data
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda : datetime.utcnow() - timedelta(days=17)
)
# Ticker data for orders, trades and positions
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
)
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        api_key="<your api key>",
        secret_key="<your secret key>",
        trading_symbol="EUR"
    )
)


@app.strategy(
    # Run every two hours
    time_unit=TimeUnit.HOUR, 
    interval=2, 
    # Specify market data sources that need to be passed to the strategy
    market_data_sources=[bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]
)
def perform_strategy(algorithm: Algorithm, market_data):
    print(
        f"Performing trading strategy on market " +
        f"data {market_data[bitvavo_btc_eur_ohlcv_2h.get_identifier()]}"
    )

if __name__ == "__main__":
    app.run()
```

> You can find more examples [here](./examples) folder.

## Backtesting
The framework also supports backtesting. You can use the same code as above,
but instead of running the algorithm, you can run a backtest.

```python
import pathlib
from datetime import datetime, timedelta
from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TimeUnit, CCXTOHLCVMarketDataSource, Algorithm, pretty_print_backtest, \
    CCXTTickerMarketDataSource, BacktestPortfolioConfiguration

# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h", 
    start_date_func=lambda : datetime.utcnow() - timedelta(days=17) 
)
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC",
    market="BITVAVO",
    symbol="BTC/EUR",
    backtest_timeframe="2h" # We want the ticker data to 
    # be sampled every 2 hours, inline with the strategy interval
)
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)

@app.strategy(
    time_unit=TimeUnit.HOUR, 
    interval=2, 
    market_data_sources=[bitvavo_btc_eur_ohlcv_2h]
)
def perform_strategy(algorithm: Algorithm, market_data):
    print(
        f"Performing trading strategy on market " +
        f"data {market_data[bitvavo_btc_eur_ohlcv_2h.get_identifier()]}"
    )

if __name__ == "__main__":
    app.add_portfolio_configuration(BacktestPortfolioConfiguration(
        unallocated=400,
        market="BITVAVO",
        trading_symbol="EUR",
    ))
    backtest_report = app.backtest(
        start_date=datetime(2023, 11, 12) - timedelta(days=10),
        end_date=datetime(2023, 11, 12),
    )
    pretty_print_backtest(backtest_report)
```
For more examples, check out the [examples](./examples/backtesting) folder.

### Backtesting report
You can use the ```pretty_print_backtest``` function to print a backtesting report.
For example if you run the [moving average example trading bot](./examples/backtesting/moving_average.py)
you will get the following backtesting report:
 
```bash
====================Backtest report===============================
* Start date: 2021-04-03 00:00:00
* End date: 2021-06-26 00:00:00
* Number of days: 84
* Number of runs: 1009
====================Portfolio overview============================
* Number of orders: 24
* Initial balance: 400.0000 EUR
* Final balance: 380.7132 EUR
* Total net gain: -19.2868 EUR
* Total net gain percentage: -4.8217%
* Growth rate: -4.8217%
* Growth -19.2868 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  380.713 │                0 │      380.713 │       380.713 │ 100.0000%                 │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 12
* Number of trades open: 0
* Percentage of positive trades: 25.0%
* Percentage of negative trades: 75.0%
* Average trade size: 96.9068 EUR
* Average trade duration: 69.16666666666667 hours
╭─────────┬─────────────────────┬─────────────────────┬────────────────────┬──────────────┬──────────────────┬───────────────────────┬────────────────────┬─────────────────────╮
│ Pair    │ Open date           │ Close date          │   Duration (hours) │   Size (EUR) │   Net gain (EUR) │ Net gain percentage   │   Open price (EUR) │   Close price (EUR) │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-06-24 14:00:00 │ 2021-06-25 22:00:00 │                 32 │      93.786  │          -5.0787 │ -5.4152%              │              28420 │               26881 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-06-23 16:00:00 │ 2021-06-23 20:00:00 │                  4 │      95.9956 │          -1.3022 │ -1.3565%              │              28234 │               27851 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-06-13 20:00:00 │ 2021-06-17 06:00:00 │                 82 │      96.501  │           1.014  │ 1.0508%               │              32167 │               32505 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-06-09 20:00:00 │ 2021-06-12 18:00:00 │                 70 │      95.3472 │          -1.424  │ -1.4935%              │              29796 │               29351 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-05-31 20:00:00 │ 2021-06-04 18:00:00 │                 94 │      96.4384 │           1.0432 │ 1.0817%               │              30137 │               30463 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-05-24 20:00:00 │ 2021-05-28 10:00:00 │                 86 │      97.476  │          -6.732  │ -6.9063%              │              32492 │               30248 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-05-07 16:00:00 │ 2021-05-10 22:00:00 │                 78 │      95.296  │          -4.578  │ -4.8040%              │              47648 │               45359 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-05-05 22:00:00 │ 2021-05-07 06:00:00 │                 32 │      99.4392 │          -2.4423 │ -2.4561%              │              47352 │               46189 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-04-30 14:00:00 │ 2021-05-04 06:00:00 │                 88 │      97.4694 │          -0.1974 │ -0.2025%              │              46414 │               46320 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-04-26 10:00:00 │ 2021-04-29 20:00:00 │                 82 │      97.3544 │          -1.6874 │ -1.7333%              │              44252 │               43485 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-04-09 10:00:00 │ 2021-04-16 12:00:00 │                170 │      98.1    │           3.82   │ 3.8940%               │              49050 │               50960 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2021-04-06 04:00:00 │ 2021-04-06 16:00:00 │                 12 │      99.678  │          -1.722  │ -1.7276%              │              49839 │               48978 │
╰─────────┴─────────────────────┴─────────────────────┴────────────────────┴──────────────┴──────────────────┴───────────────────────┴────────────────────┴─────────────────────╯
==================================================================
```

## Broker/Exchange configuration
The framework has by default support for [ccxt](https://github.com/ccxt/ccxt).
This should allow you to connect to a lot of brokers/exchanges.

```python
from investing_algorithm_framework import App, PortfolioConfiguration
app = App()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO", 
        api_key="xxxx", 
        secret_key="xxxx", 
        track_from="01/01/2022",
        trading_symbol="EUR"
    )
)
```

## Download
You can download the framework with pypi.

```bash
pip install investing-algorithm-framework
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

For further information regarding usage and licensing we recommend going 
to the licensing page at the website.

## Documentation

All the documentation can be found online 
at the [documentation webstie](https://investing-algorithm-framework.com)

In most cases, you'll probably never have to change code on this repo directly 
if you are building your algorithm/bot. But if you do, check out the 
contributing page at the website.

If you'd like to chat with investing-algorithm-framework users 
and developers, [join us on Slack](https://inv-algo-framework.slack.com) or [join us on reddit](https://www.reddit.com/r/InvestingBots/)

## Acknowledgements
We want to thank all contributors to this project. A full list of all 
the people that contributed to the project can be
found [here](https://github.com/investing-algorithms/investing-algorithm-framework/blob/master/AUTHORS.md)

### [Bugs / Issues](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)

If you discover a bug in the framework, please [search our issue tracker](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)
first. If it hasn't been reported, please [create a new issue](https://github.com/investing-algorithms/investing-algorithm-framework/issues/new).

### Contributing
Feel like the framework is missing a feature? We welcome your pull requests!
If you want to contribute to the project roadmap, please take a look at the [project board](https://github.com/coding-kitties/investing-algorithm-framework/projects?query=is%3Aopen).
You can pick up a task by assigning yourself to it. 

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do*.
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `master`.
