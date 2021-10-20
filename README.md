[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)

# Investing Algorithm Framework

> :warning: **Documentation outdated**: We are working hard on releasing v1.0.0. After 
> this release we will update the documentation at the website.

The Investing Algorithm Framework is a python framework for building
investment algorithms. It encourages rapid development and clean, pragmatic code design.

The framework provides you with an all the components you need to create an 
investing algorithm (data providing, portfolio management, order execution, etc..). 
Also, the algorithm can be controlled with a REST Api that will run in the background.


## Example Algorithm for Binance
```python
import os

from investing_algorithm_framework import App, TimeUnit, AlgorithmContext, \
    TradingDataTypes
from investing_algorithm_framework.configuration.constants import BINANCE, \
    BINANCE_API_KEY, BINANCE_SECRET_KEY, TRADING_SYMBOL

BTC_SYMBOL = "BTC"

# Our trading symbol (e.g. dot/usdt, sol/usdt)
USDT_SYMBOL = "USDT"

# Make the parent dir your resources directory (database, csv storage)
dir_path = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

# Create an application (setups your algorithm, database, rest api, etc...)
app = App(
    resources_directory=dir_path,
    config={
        BINANCE_API_KEY: "<BINANCE_API_KEY>",
        BINANCE_SECRET_KEY: "<BINANCE_SECRET_KEY>",
        TRADING_SYMBOL: USDT_SYMBOL,
    }
)


# Algorithm strategy that runs every 5 minutes
@app.algorithm.schedule(time_unit=TimeUnit.MINUTE, interval=5)
def perform_strategy(context: AlgorithmContext):
    # Get ticker data from binance
    ticker = context.get_data(
        BINANCE,
        trading_data_type=TradingDataTypes.TICKER,
        target_symbol=BTC_SYMBOL,
    )

    if ticker.ask_price > 50000:
        # Execute a market order on binance
        context.create_market_buy_order(
            BINANCE, BTC_SYMBOL, amount_trading_symbol=10, execute=True
        )


if __name__ == "__main__":
    app.start()
```
The goal of the framework is to provide you with a set of components for 
your algorithm that takes care of a wide variety of operational processes 
out of the box.

* Data providing
* Order execution
* Portfolio management
* Performance tracking
* Strategy scheduling
* Resource management
* Model snapshots
* Order status management
* Clients (Rest API)

However, we aim to also provide a modular framework where you can write your
own components or use third party plugins for the framework.

Further information and the complete documentation can be found at the [webstie](https://investing-algorithm-framework.com)


## Download
You can download the framework with pypi.

```bash
pip install investing-algorithm-framework
```

#### Disclaimer
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

All the documentation can be found online at the [documentation webstie](https://investing-algorithm-framework.com)

In most cases, you'll probably never have to change code on this repo directly 
if you are building your algorithm/bot. But if you do, check out the 
contributing page at the website.

If you'd like to chat with investing-algorithm-framework users 
and developers, [join us on Slack](https://inv-algo-framework.slack.com) or [join us on reddit](https://www.reddit.com/r/InvestingAlgorithms/)

## Acknowledgements
We want to thank all contributors to this project. A full list of all 
the people that contributed to the project can be
found [here](https://github.com/investing-algorithms/investing-algorithm-framework/blob/master/docs/AUTHORS.md)

### Help / Slack

For any questions not covered by the documentation or for further
information about the framework, we encourage you to join our slack channel.

[join us on Slack](https://inv-algo-framework.slack.com)

### [Bugs / Issues](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)

If you discover a bug in the framework, please [search our issue tracker](https://github.com/investing-algorithms/investing-algorithm-framework/issues?q=is%3Aissue)
first. If it hasn't been reported, please [create a new issue](https://github.com/investing-algorithms/investing-algorithm-framework/issues/new).

Feel like the framework is missing a feature? We welcome your pull requests!

Please read our [Contributing document](https://github.com/investing-algorithms/investing-algorithm-framework/blob/master/docs/CONTRIBUTING.md)
to understand the requirements before sending your pull-requests.

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do* or talk to us on [Slack](https://join.slack.com/t/investingbots/shared_invite/enQtODgwNTg3MzA2MjYyLTdiZjczZDRlNWJjNDdmYThiMGE0MzFhOTg4Y2E0NzQ2OTgxYjA1NzU3ZWJiY2JhOTE1ZGJlZGFiNDU3OTAzMDg).
This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your feature or hotfix against the `develop` branch, not `master`.
