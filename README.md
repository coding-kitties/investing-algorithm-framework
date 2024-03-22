<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)
<a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a> <br/>
[![GitHub stars](https://img.shields.io/github/stars/coding-kitties/investing-algorithm-framework.svg?style=social&label=Star&maxAge=1)](https://github.com/SeaQL/sea-orm/stargazers/) If you like what we do, consider starring, sharing and contributing!

###### Sponsors
<p align="left">
<a href="https://finterion.com">
  <img alt="Finterion" src="static/sponsors/finterion.png" width="200px" />
</a>
</p>

# [Investing Algorithm Framework](https://github.com/coding-kitties/investing-algorithm-framework)

The Investing Algorithm Framework is a Python tool that enables swift and 
elegant development of trading bots. It comes with all the necessary 
components for creating algorithms, including data provisioning, 
portfolio management, and order execution.

Features: 
* Order execution
* Broker and exchange connections through [ccxt](https://github.com/ccxt/ccxt)
* Backtesting and performance analysis reports [example](./examples/backtesting)
* Backtest experiments to optimize your trading strategy [example](./examples/backtesting/backtest_experiments)
* Portfolio management
* Web API for interacting with your deployed trading bot
* Data persistence through sqlite db or an in-memory db
* Stateless running for cloud function deployments
* Polars dataframes support out of the box for fast data processing [pola.rs](https://pola.rs/)

## Example implementation
The following algorithm connects to binance and buys BTC every 5 seconds. 
It also exposes an REST API that allows you to interact with the algorithm.
```python
import pathlib
from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, CCXTOHLCVMarketDataSource, Algorithm, \
    CCXTTickerMarketDataSource, MarketCredential

# Define market data sources
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    window_size=200
)
# Ticker data for orders, trades and positions
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)
app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
algorithm = Algorithm()

app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_market_credential(MarketCredential(
    market="bitvavo",
    api_key="<your api key>",
    secret_key="<your secret key>",
))
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo",
        trading_symbol="EUR",
        initial_balance=400
    )
)
app.add_algorithm(algorithm)

@algorithm.strategy(
    # Run every two hours
    time_unit=TimeUnit.HOUR, 
    interval=2, 
    # Specify market data sources that need to be passed to the strategy
    market_data_sources=["BTC-ticker", "BTC-ohlcv"]
)
def perform_strategy(algorithm: Algorithm, market_data: dict):
    # By default, ohlcv data is passed as polars df in the form of
    # {"<identifier>": <dataframe>}  https://pola.rs/, 
    # call to_pandas() to convert to pandas
    polars_df = market_data["BTC-ohlcv"]  
    print(f"I have access to {len(polars_df)} candles of ohlcv data")

    # Ticker data is passed as {"<identifier>": <ticker dict>}
    ticker_data = market_data["BTC-ticker"]
    
    algorithm.create_limit_order(
        target_symbol="BTC/EUR",
        order_side="buy",
        amount=0.01,
        price=ticker_data["ask"],
    )
    
if __name__ == "__main__":
    app.run()
```

> You can find more examples [here](./examples) folder.

## Backtesting and experiments
The framework also supports backtesting and performing backtest experiments. After 
a backtest, you can print a report that shows the performance of your trading bot.

To run a single backtest you can use the example code that can be found [here](./examples/backtest).

### Backtesting report
You can use the ```pretty_print_backtest``` function to print a backtest report.
For example if you run the [moving average example trading bot](./examples/crossover_moving_average_trading_bot)
you will get the following backtesting report:
 
```bash
====================Backtest report===============================
* Start date: 2023-08-24 00:00:00
* End date: 2023-12-02 00:00:00
* Number of days: 100
* Number of runs: 1201
====================Portfolio overview============================
* Number of orders: 40
* Initial balance: 400.0000 EUR
* Final balance: 425.9722 EUR
* Total net gain: 25.9722 EUR
* Total net gain percentage: 6.4931%
* Growth rate: 6.4931%
* Growth 25.9722 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────────┬───────────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending buy amount │   Pending sell amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  425.972 │                    0 │                     0 │      425.972 │       425.972 │ 100.0000%                 │              0 │ 0.0000%       │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ DOT        │    0     │                    0 │                     0 │        0     │         0     │ 0.0000%                   │              0 │ 0.0000%       │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ BTC        │    0     │                    0 │                     0 │        0     │         0     │ 0.0000%                   │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────────┴───────────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 20
* Number of trades open: 0
* Percentage of positive trades: 40.0%
* Percentage of negative trades: 60.0%
* Average trade size: 100.4738 EUR
* Average trade duration: 83.6 hours
╭─────────┬─────────────────────┬─────────────────────┬────────────────────┬──────────────┬──────────────────┬───────────────────────┬────────────────────┬─────────────────────╮
│ Pair    │ Open date           │ Close date          │   Duration (hours) │   Size (EUR) │   Net gain (EUR) │ Net gain percentage   │   Open price (EUR) │   Close price (EUR) │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-24 14:00:00 │ 2023-11-27 16:00:00 │                 74 │     107.061  │          -2.2734 │ -2.1234%              │             4.78   │              4.6785 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-20 02:00:00 │ 2023-11-21 10:00:00 │                 32 │     109.269  │          -4.933  │ -4.5145%              │             4.995  │              4.7695 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-20 00:00:00 │ 2023-11-22 02:00:00 │                 50 │     105.992  │          -3.8994 │ -3.6789%              │         34190.9    │          32933.1    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-06 14:00:00 │ 2023-11-13 16:00:00 │                170 │     104.838  │           5.4049 │ 5.1555%               │         32761.8    │          34450.9    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-20 14:00:00 │ 2023-10-27 10:00:00 │                164 │      98.8999 │          11.4752 │ 11.6028%              │             3.525  │              3.934  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-10-14 06:00:00 │ 2023-10-28 00:00:00 │                330 │      97.2734 │          24.5982 │ 25.2876%              │         25598.3    │          32071.5    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-14 06:00:00 │ 2023-10-17 16:00:00 │                 82 │      99.2141 │          -1.2575 │ -1.2674%              │             3.5505 │              3.5055 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-07 10:00:00 │ 2023-10-08 10:00:00 │                 24 │      99.6325 │          -1.6732 │ -1.6794%              │             3.8705 │              3.8055 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-27 12:00:00 │ 2023-10-05 22:00:00 │                202 │      96.3253 │           2.7092 │ 2.8126%               │         25348.8    │          26061.7    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-27 12:00:00 │ 2023-10-03 22:00:00 │                154 │      98.6987 │           1.0253 │ 1.0388%               │             3.8505 │              3.8905 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-25 14:00:00 │ 2023-09-27 06:00:00 │                 40 │      99.0277 │          -1.315  │ -1.3280%              │             3.8405 │              3.7895 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-14 18:00:00 │ 2023-09-18 04:00:00 │                 82 │      98.9598 │           0.2715 │ 0.2744%               │             3.8265 │              3.837  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-07 08:00:00 │ 2023-09-10 18:00:00 │                 82 │      98.5979 │           0.1801 │ 0.1827%               │         24048.3    │          24092.2    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-07 02:00:00 │ 2023-09-09 04:00:00 │                 50 │      99.0076 │          -0.3719 │ -0.3757%              │             3.993  │              3.978  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-05 16:00:00 │ 2023-09-06 14:00:00 │                 22 │      99.1603 │          -0.61   │ -0.6152%              │             3.9825 │              3.958  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-04 18:00:00 │ 2023-09-05 00:00:00 │                  6 │      99.3611 │          -0.8044 │ -0.8096%              │             3.9525 │              3.9205 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-09-04 12:00:00 │ 2023-09-04 16:00:00 │                  4 │      99.5219 │          -0.6427 │ -0.6458%              │             3.9485 │              3.923  │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-08-26 12:00:00 │ 2023-08-26 20:00:00 │                  8 │      98.9954 │           0.0268 │ 0.0271%               │         24145.2    │          24151.8    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-08-25 12:00:00 │ 2023-08-28 12:00:00 │                 72 │      99.6416 │          -0.5051 │ -0.5069%              │             4.1425 │              4.1215 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-08-24 02:00:00 │ 2023-08-25 02:00:00 │                 24 │      99.9997 │          -1.4334 │ -1.4334%              │             4.151  │              4.0915 │
╰─────────┴─────────────────────┴─────────────────────┴────────────────────┴──────────────┴──────────────────┴───────────────────────┴────────────────────┴─────────────────────╯
==================================================================
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
        track_from="01/01/2022",
        trading_symbol="EUR"
    )
)
```

## Performance
We are continuously working on improving the performance of the framework. If
you have any suggestions, please let us know.

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
The investing algorithm framework is a community driven project. 
We welcome you to participate, contribute and together help build 
the future trading bots developed in python.

Feel like the framework is missing a feature? We welcome your pull requests!
If you want to contribute to the project roadmap, please take a look at the [project board](https://github.com/coding-kitties/investing-algorithm-framework/projects?query=is%3Aopen).
You can pick up a task by assigning yourself to it. 

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do*.
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `master`.
