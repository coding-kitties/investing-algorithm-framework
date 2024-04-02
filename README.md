<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/publish.yml)
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
* Backtesting and performance analysis reports [example](./examples/backtest)
* Backtest experiments to optimize your trading strategy [example](./examples/backtest_experiment)
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
    CCXTTickerMarketDataSource, MarketCredential, SYMBOLS

# Define the symbols you want to trade for optimization, otherwise the 
# algorithm will check if you have orders and balances on all available 
# symbols on the market
symbols = ["BTC/EUR"]

# Define resource directory and the symbols you want to trade
config = {
    RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()
    SYMBOLS: symbols
}

# Define market data sources
# OHLCV data for candles
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
app = create_app(config=config)
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
    unallocated_balance = algorithm.get_unallocated()
    positions = algorithm.get_positions()
    trades = algorithm.get_trades()
    open_trades = algorithm.get_open_trades()
    closed_trades = algorithm.get_closed_trades()
    
    # Create a buy oder 
    algorithm.create_limit_order(
        target_symbol="BTC/EUR",
        order_side="buy",
        amount=0.01,
        price=ticker_data["ask"],
    )
    
    # Close a trade
    algorithm.close_trade(trades[0].id)
    
    # Close a position
    algorithm.close_position(positions[0].get_symbol())
    
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
* Number of orders: 10
* Initial balance: 400.0000 EUR
* Final balance: 431.8837 EUR
* Total net gain: 28.4171 EUR
* Total net gain percentage: 7.1043%
* Growth rate: 7.9709%
* Growth 31.8837 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────────┬───────────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending buy amount │   Pending sell amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │ 214.219  │                    0 │                     0 │      214.219 │       214.219 │ 49.6010%                  │         0      │ 0.0000%       │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ BTC        │   0.0031 │                    0 │                     0 │      107.095 │       110.401 │ 25.5627%                  │         3.3066 │ 3.0875%       │
├────────────┼──────────┼──────────────────────┼───────────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ DOT        │  21.3291 │                    0 │                     0 │      107.104 │       107.264 │ 24.8363%                  │         0.16   │ 0.1494%       │
╰────────────┴──────────┴──────────────────────┴───────────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 4
* Number of trades open: 2
* Percentage of positive trades: 60.0%
* Percentage of negative trades: 20.0%
* Average trade size: 98.8728 EUR
* Average trade duration: 183.5 hours
╭─────────┬─────────────────────┬─────────────────────┬────────────────────┬──────────────┬──────────────────┬───────────────────────┬────────────────────┬─────────────────────╮
│ Pair    │ Open date           │ Close date          │   Duration (hours) │   Size (EUR) │   Net gain (EUR) │ Net gain percentage   │   Open price (EUR) │   Close price (EUR) │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-11-30 20:00:00 │                     │            2976.65 │     107.104  │           0      │ 0.0000%               │             5.0215 │                     │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-29 14:00:00 │                     │            3006.65 │     107.095  │           0      │ 0.0000%               │         34546.6    │                     │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-08 00:00:00 │ 2023-11-14 16:00:00 │             160    │      99.2265 │           1.3352 │ 1.3456%               │         33075.5    │          33520.6    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-11-06 16:00:00 │ 2023-11-06 20:00:00 │               4    │      97.8607 │          -0.0026 │ -0.0026%              │         32620.2    │          32619.4    │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ DOT-EUR │ 2023-10-30 06:00:00 │ 2023-11-14 00:00:00 │             354    │     100.551  │          24.8794 │ 24.7430%              │             4.0375 │              5.0365 │
├─────────┼─────────────────────┼─────────────────────┼────────────────────┼──────────────┼──────────────────┼───────────────────────┼────────────────────┼─────────────────────┤
│ BTC-EUR │ 2023-09-13 16:00:00 │ 2023-09-22 16:00:00 │             216    │      97.8529 │           2.2051 │ 2.2534%               │         24463.2    │          25014.5    │
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
