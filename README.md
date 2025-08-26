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

The Investing Algorithm Framework is a Python-based framework built to streamline the entire lifecycle of quantitative trading strategies from signal generation and backtesting to live deployment.
It offers a complete quantitative workflow, featuring two dedicated backtesting engines:

* A vectorized backtest engine for fast signal research and prototyping

* An event-based backtest engine for realistic and accurate strategy evaluation

The framework supports live trading across multiple exchanges and offers flexible deployment options, including Azure Functions and AWS Lambda.
Designed for extensibility, it allows you to integrate custom strategies, data providers, and order executors, enabling support for any exchange or broker.
It natively supports multiple data formats, including OHLCV, ticker, and custom datasets with seamless compatibility for both Pandas and Polars DataFrames.



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
- [x] Event-Driven Backtest Engine: Accurate and realistic backtesting with event-driven architecture.
- [x] Vectorized Backtest Engine: Fast signal research and prototyping with vectorized operations.
- [x] Permutation testing: Run permutation tests to evaluate the strategy statistical significance.
- [x] Backtest Reporting: Generate detailed reports to analyse and compare backtests.
- [x] Live Trading: Execute trades in real-time with support for multiple exchanges via ccxt.
- [x] Portfolio Management: Manage portfolios, trades, and positions with persistence via SQLite.
- [x] Market Data Sources: Fetch OHLCV, ticker, and custom data with support for Polars and Pandas.
- [x] Azure Functions Support: Deploy trading bots to Azure.
- [x] AWS Lambda Support: Deploy trading bots to AWS Lambda.
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

from pyindicators import ema, rsi, crossunder, crossover, is_above

from investing_algorithm_framework import create_app, TimeUnit, Context, BacktestDateRange, \
    DEFAULT_LOGGING_CONFIG, TradingStrategy, SnapshotInterval, BacktestReport, DataSource

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
logger = logging.getLogger(__name__)

app = create_app()
# Registered bitvavo market, credentials are read from .env file by default
app.add_market(market="BITVAVO", trading_symbol="EUR", initial_balance=100)

class MyStrategy(TradingStrategy):
    interval = 2
    time_unit = TimeUnit.HOUR
    data_sources = [
        DataSource(data_type="OHLCV", market="bitvavo", symbol="BTC/EUR", window_size=200, time_frame="2h", identifier="BTC-ohlcv", pandas=True),
    ]
    symbols = ["BTC/EUR"]

    def run_strategy(self, context: Context, data):

        if context.has_open_orders(target_symbol="BTC"):
            logger.info("There are open orders, skipping strategy iteration.")
            return

        data = data["BTC-ohlcv"]
        data = ema(data, source_column="Close", period=20, result_column="ema_20")
        data = ema(data, source_column="Close", period=50, result_column="ema_50")
        data = ema(data, source_column="Close", period=100, result_column="ema_100")
        data = crossunder(data, first_column="ema_50", second_column="ema_100", result_column="crossunder_50_20")
        data = crossover(data, first_column="ema_50", second_column="ema_100", result_column="crossover_50_20")
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

    def buy_signal(self, data) -> bool:
        return False

    def sell_signal(self, data) -> bool:
        return False

date_range = BacktestDateRange(
    start_date="2023-08-24 00:00:00", end_date="2023-12-02 00:00:00"
)
app.add_strategy(MyStrategy)

if __name__ == "__main__":
    # Run the backtest with a daily snapshot interval for end-of-day granular reporting
    backtest = app.run_backtest(
        backtest_date_range=date_range, initial_amount=100, snapshot_interval=SnapshotInterval.DAILY
    )
    backtest_report = BacktestReport(backtests=[backtest])
    backtest_report.show()
```

> You can find more examples [here](./examples) folder.

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
