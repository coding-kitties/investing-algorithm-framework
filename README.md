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
You can use the ```pretty_print_backtest``` function to print a backtest report.
For example if you run the [moving average example trading bot](./examples/backtesting/moving_average.py)
you will get the following backtesting report:
 
```bash
====================Backtest report===============================
* Start date: 2023-08-24 00:00:00
* End date: 2023-12-02 00:00:00
* Number of days: 100
* Number of runs: 1201
====================Portfolio overview============================
* Number of orders: 41
* Initial balance: 400.0000 EUR
* Final balance: 440.9081 EUR
* Total net gain: 40.4219 EUR
* Total net gain percentage: 10.1055%
* Growth rate: 10.2270%
* Growth 40.9081 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │ 330.317  │                0 │      330.317 │       330.317 │ 74.9174%                  │         0      │ 0.0000%       │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ DOT        │  22.0034 │                0 │      110.105 │       110.591 │ 25.0826%                  │         0.4863 │ 0.4416%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 20
* Number of trades open: 1
* Percentage of positive trades: 39.02439024390244%
* Percentage of negative trades: 58.536585365853654%
* Average trade size: 101.5585 EUR
* Average trade duration: 92.5 hours
╭─────────┬─────────────────────┬─────────────────────┬────────────────────┬──────────────┬──────────────────┬───────────────────────┬────────────────────┬─────────────────────╮
│ Pair    │ Open date           │ Close date          │   Duration (hours) │   Size (EUR) │   Net gain (EUR) │ Net gain percentage   │   Open price (EUR) │   Close price (EUR) │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-30 16:00:00 │                     │            259.148 │     110.105  │           0      │ 0.0000%               │             5.004  │                     │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-24 12:00:00 │ 2023-11-27 14:00:00 │             74     │     110.725  │          -2.4793 │ -2.2392%              │             4.7964 │              4.689  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-20 00:00:00 │ 2023-11-21 08:00:00 │             32     │     111.695  │          -3.8798 │ -3.4735%              │             4.9805 │              4.8075 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-16 20:00:00 │ 2023-11-20 00:00:00 │             76     │     109.263  │           2.5245 │ 2.3105%               │         33110      │          33875      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-06 10:00:00 │ 2023-11-13 14:00:00 │            172     │     107.996  │           5.7387 │ 5.3138%               │         32726      │          34465      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-20 12:00:00 │ 2023-10-27 08:00:00 │            164     │     100.652  │          11.2336 │ 11.1608%              │             3.5526 │              3.9491 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-10-14 04:00:00 │ 2023-10-27 22:00:00 │            330     │      99.957  │          24.6753 │ 24.6859%              │         25630      │          31957      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-14 04:00:00 │ 2023-10-17 14:00:00 │             82     │     100.946  │          -1.1753 │ -1.1643%              │             3.5643 │              3.5228 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-07 08:00:00 │ 2023-10-08 06:00:00 │             22     │     101.211  │          -1.0607 │ -1.0480%              │             3.874  │              3.8334 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-27 10:00:00 │ 2023-10-05 20:00:00 │            202     │      97.4688 │           4.0365 │ 4.1413%               │         24992      │          26027      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-27 10:00:00 │ 2023-10-03 22:00:00 │            156     │      99.7074 │           1.9774 │ 1.9832%               │             3.8271 │              3.903  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-25 12:00:00 │ 2023-09-27 04:00:00 │             40     │      99.7994 │          -0.3672 │ -0.3679%              │             3.8052 │              3.7912 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-14 18:00:00 │ 2023-09-18 02:00:00 │             80     │      99.4298 │          -0.1612 │ -0.1621%              │             3.8244 │              3.8182 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-12 16:00:00 │ 2023-09-21 18:00:00 │            218     │      98.008  │           1.64   │ 1.6733%               │         24502      │          24912      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-07 02:00:00 │ 2023-09-10 16:00:00 │             86     │      98.4656 │           0.4592 │ 0.4664%               │         24016      │          24128      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-07 00:00:00 │ 2023-09-09 02:00:00 │             50     │      99.3915 │          -0.307  │ -0.3089%              │             3.982  │              3.9697 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-06 00:00:00 │ 2023-09-06 12:00:00 │             12     │      98.5558 │          -0.3116 │ -0.3162%              │         24038      │          23962      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-05 12:00:00 │ 2023-09-06 16:00:00 │             28     │      99.6655 │          -0.7846 │ -0.7872%              │             3.9759 │              3.9446 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-04 18:00:00 │ 2023-09-04 22:00:00 │              4     │      98.2565 │          -0.0164 │ -0.0167%              │         23965      │          23961      │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-04 08:00:00 │ 2023-09-04 22:00:00 │             14     │      99.9766 │          -1.2274 │ -1.2277%              │             3.9748 │              3.926  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-08-25 02:00:00 │ 2023-08-25 10:00:00 │              8     │      99.9996 │          -0.0928 │ -0.0928%              │             4.0968 │              4.093  │
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
