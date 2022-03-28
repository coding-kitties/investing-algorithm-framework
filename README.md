<a href=https://investing-algorithm-framework.com><img src="https://img.shields.io/badge/docs-website-brightgreen"></a>
[![Build](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml/badge.svg)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/build.yml)
[![Tests](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/investing-algorithm-framework)](https://pepy.tech/badge/investing-algorithm-framework)
[![Current Version](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)](https://img.shields.io/pypi/v/investing_algorithm_framework.svg)
<a href="https://www.reddit.com/r/InvestingBots/"><img src="https://img.shields.io/reddit/subreddit-subscribers/investingbots?style=social"></a>
###### Sponsors
<p align="left">
<a href="https://eltyer.com">
  <img src="https://eltyer-production.s3.eu-central-1.amazonaws.com/logos/eltyer-logo.svg" width="200px" />
</a>
</p>

# Investing Algorithm Framework
The Investing Algorithm Framework is a python framework for building
investment algorithms. It encourages rapid development and clean, pragmatic code design.

The framework provides you with an all the components you need to create an 
investing algorithm (data providing, portfolio management, order execution, etc..). 
Also, the algorithm can be controlled with a REST Api that will run in the background.


## Example Algorithm for Binance
```python
import os
from investing_algorithm_framework import App, AlgorithmContext

# Set parent dir as resources' directory (database, manage.py)
dir_path = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

# Create an application (manages your algorithm, rest api, etc...)
app = App(
    resource_directory=dir_path,
    config={
        "PORTFOLIOS": {
            "MY_PORTFOLIO": {
                "API_KEY": "<YOUR_API_KEY>",
                "SECRET_KEY": "<YOUR_SECRET_KEY>",
                "TRADING_SYMBOL": "USDT",
                "MARKET": "BINANCE",
            }
        }
    }
)


# Algorithm strategy that runs every 5 seconds and gets the ticker of BTC from BINANCE
@app.algorithm.strategy(
    time_unit="MINUTE",
    interval=5,
    market="BINANCE",
    target_symbol="BTC",
    trading_symbol="USDT",
    trading_data_type="OHLCV",
    limit=100,
    trading_time_unit="ONE_DAY"
)
def perform_strategy(context: AlgorithmContext, ohlcv):
    print(context.get_unallocated("MY_PORTFOLIO"))
    print(ohlcv)

if __name__ == "__main__":
    app.start()
```

> **NOTE:** The framework is in **alpha**.

The example algorithm makes use of the default data provider, order executor and 
portfolio manager for BINANCE. However, your can also define your own 
components for your algorithm making it compatible to any broker of choice.

The goal of the framework is to provide you with a set of components for 
your algorithm that takes care of a wide variety of operational processes 
out of the box.


## Features

- **Data Providing**  
- **Order execution** 
- **Portfolio management**
- **Performance tracking**
- **Strategy scheduling**
- **Resource management**
- **Historic portfolio snapshots**
- **Order status management**
- **Clients (Rest API)**

However, we aim to also provide a modular framework where you can write your
own components or use third party plugins for the framework.

Further information and the complete documentation can be found 
at the [website](https://investing-algorithm-framework.com)


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
