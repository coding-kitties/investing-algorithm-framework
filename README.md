<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)
<a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a>
###### Sponsors
<p align="left">
<a href="https://logicfunds.io">
  <img alt="logicfunds" src="https://logicfunds-web-app-images.s3.eu-central-1.amazonaws.com/logicfunds-logo.png" width="200px" />
</a>
</p>


# [Investing Algorithm Framework](https://github.com/coding-kitties/investing-algorithm-framework)

The Investing Algorithm Framework is a Python tool that enables swift and 
elegant development of investment algorithms and trading bots. It comes with all the necessary 
components for creating algorithms, including data provisioning, portfolio management, and order execution.


## Example
The following algorithm connects to binance and buys BTC every 5 seconds. 
It also exposes an REST API that allows you to interact with the algorithm.
```python
import pathlib
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, TimeUnit, TradingTimeFrame, TradingDataType, OrderSide

app = create_app({RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()})
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="binance",
        api_key="xxxxxx",
        secret_key="xxxxxx",
        trading_symbol="USDT"
    )
)


@app.strategy(
    time_unit=TimeUnit.SECOND, # Algorithm will be executed every 5 seconds
    interval=5,
    market="binance", # Will retrieve trading data from binance
    symbols=["BTC/USDT", "ETH/USDT", ["DOT/USDT"]], # Symbols must be in the format of TARGET/TRADE symbol (e.g. BTC/USDT)
    trading_data_types=[TradingDataType.OHLCV, TradingDataType.TICKER, TradingDataType.ORDER_BOOK],
    trading_time_frame_start_date=datetime.utcnow() - timedelta(days=1), # Will retrieve data from the last 24 hours
    trading_time_frame=TradingTimeFrame.ONE_MINUTE # Will retrieve data on 1m interval (OHLCV)
)
def perform_strategy(algorithm, market_data):
    print(algorithm.get_allocated())
    print(algorithm.get_unallocated())
    print(market_data)
    algorithm.create_limit_order(
        target_symbol="BTC", 
        side=OrderSide.BUY,
        price=market_data["TICKER"]["BTC/USDT"]["BID"], 
        amount_target_symbol=0.00001
    )


if __name__ == "__main__":
    app.run()
```

> You can find more examples [here](./examples) folder.

## Broker/Exchange configuration
The framework has by default support for [ccxt](https://github.com/ccxt/ccxt).
This should allow you to connect to a lot of brokers/exchanges.

```python
from investing_algorithm_framework import App, PortfolioConfiguration
app = App()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="bitvavo", 
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

Feel like the framework is missing a feature? We welcome your pull requests!

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do*.
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `master`.
