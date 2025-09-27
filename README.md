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
- [x] Metric tracking and backtest reports evaluation/comparison: Track and compare key performance metrics like CAGR, Sharpe ratio, max drawdown, and more (See example usage for a complete list of metrics the framework collects).
- [x] Backtest Reporting: Generate detailed reports to analyse and compare backtests.
- [x] Live Trading: Execute trades in real-time with support for multiple exchanges via ccxt.
- [x] Portfolio Management: Manage portfolios, trades, and positions with persistence via SQLite.
- [x] Market Data Sources: Fetch OHLCV, ticker, and custom data with support for Polars and Pandas.
- [x] Azure Functions Support: Deploy trading bots to Azure.
- [x] AWS Lambda Support: Deploy trading bots to AWS Lambda.
- [x] Web API: Interact with your bot via REST API.
- [x] PyIndicators Integration: Perform technical analysis directly on your dataframes.
- [x] Extensibility: Add custom strategies, data providers, order executors so you can connect your trading bot to your favorite exchange or broker.
- [x] Modular Design: Build your bot using modular components for easy customization and maintenance.
- [x] Multiple exchanges and brokers: **Detailed guides and API references to help you get started and make the most of the framework.
 and offers flexible deployment options, including Azure Functions and AWS Lambda.
Designed for extensibility, it allows you to integrate custom strategies, data providers, and order executors, enabling support for any exchange or broker.
It natively supports multiple data formats, including OHLCV, ticker, and custom datasets with seamless compatibility for both Pandas and Polars DataFrames.



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

For a aws lambda compatible project, run:

```bash
investing-algorithm-framework init --type aws_lambda
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
from typing import Dict, Any
from datetime import datetime, timezone

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, create_app, RESOURCE_DIRECTORY, \
    BacktestDateRange, BacktestReport


class RSIEMACrossoverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(
            symbol="BTC", percentage_of_portfolio=20.0
        ),
        PositionSize(
            symbol="ETH", percentage_of_portfolio=20.0
        )
    ]

    def __init__(
        self,
        time_unit: TimeUnit,
        interval: int,
        market: str,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window: int = 10
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        data_sources = []

        for symbol in self.symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )

        super().__init__(
            data_sources=data_sources, time_unit=time_unit, interval=interval
        )

    def _prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        """
        Helper function to prepare the indicators 
        for the strategy. The indicators are calculated
        using the pyindicators library: https://github.com/coding-kitties/PyIndicators
        """
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate buy signals based on the moving average crossover.

        data (Dict[str, Any]): Dictionary containing all the data for
            the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating buy signals (True/False).
        """

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self._prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossover confirmed
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                < self.rsi_oversold_threshold

            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signals = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signals
        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (Dict[str, Any]): Dictionary containing all the data for
                the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating sell signals (True/False).
        """

        signals = {}
        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self._prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # Confirmed by crossover between short-term EMA and long-term EMA
            # within a given lookback window
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_overbought = rsi_data[self.rsi_result_column] \
               >= self.rsi_overbought_threshold

            # Combine both conditions
            sell_signal = rsi_overbought & ema_crossunder_lookback
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal
        return signals


if __name__ == "__main__":
    app = create_app()
    app.add_strategy(
        RSIEMACrossoverStrategy(
            time_unit=TimeUnit.HOUR,
            interval=2,
            market="bitvavo",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=12,
            ema_long_period=26,
            ema_cross_lookback_window=10
        )
    )

    # Market credentials for coinbase for both the portfolio connection and data sources will
    # be read from .env file, when not registering a market credential object in the app.
    app.add_market(
        market="bitvavo",
        trading_symbol="EUR",
    )
    backtest_range = BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
    )
    backtest = app.run_backtest(
        backtest_date_range=backtest_range, initial_amount=1000
    )
    report = BacktestReport(backtest)
    report.show(backtest_date_range=backtest_range, browser=True)
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
