<div align="center">
  <h1>⚡ Investing Algorithm Framework</h1>
  
  <p style="font-size: 18px; font-weight: 600; margin: 15px 0;">
    🚀 <b>Build. Backtest. Deploy.</b> Quantitative Trading Strategies at Scale
  </p>
  
  <p style="font-size: 14px; color: #666; margin-bottom: 25px;">
    The fastest way to go from trading idea to production-ready trading bot
  </p>

  <!-- Quick Links -->
  <div style="margin: 20px 0;">
    <a target="_blank" href="https://coding-kitties.github.io/investing-algorithm-framework/">
      <img src="https://img.shields.io/badge/📖_Documentation-blue?style=for-the-badge">
    </a>
    &nbsp;
    <a href="https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation">
      <img src="https://img.shields.io/badge/🚀_Quick_Start-green?style=for-the-badge">
    </a>
  </div>

  <!-- Badges -->
  <div style="margin-bottom: 20px;">
    <a target="_blank" href="https://discord.gg/dQsRmGZP"><img src="https://img.shields.io/discord/1345358169777635410.svg?color=7289da&label=Discord&logo=discord&style=flat-square" alt="Discord"></a>
    &nbsp;
    <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml"><img src="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml/badge.svg?style=flat-square" alt="Tests"></a>
    &nbsp;
    <a href="https://pypi.org/project/investing-algorithm-framework/"><img src="https://img.shields.io/pypi/v/investing-algorithm-framework.svg?style=flat-square" alt="PyPI"></a>
    &nbsp;
    <a href="https://pepy.tech/project/investing-algorithm-framework"><img src="https://pepy.tech/badge/investing-algorithm-framework/month?style=flat-square" alt="Downloads"></a>
    &nbsp;
    <a href="https://github.com/coding-kitties/investing-algorithm-framework/stargazers"><img src="https://img.shields.io/github/stars/coding-kitties/investing-algorithm-framework?style=flat-square" alt="Stars"></a>
  </div>

  <img src="static/showcase.svg" alt="Investing Algorithm Framework" style="height: 400px; max-width: 100%; margin: 30px 0;">

  <hr style="margin: 30px 0; border: none; border-top: 2px solid #ddd;">

  > ⭐ **If you like this project, please consider [starring](https://github.com/coding-kitties/investing-algorithm-framework) it!** Your support helps us build better tools for the community.

</div>

---

## 💡 Why Investing Algorithm Framework?

Stop wasting time on boilerplate. The **Investing Algorithm Framework** handles all the heavy lifting:

✨ **From Idea to Production** — Write your strategy once, deploy everywhere  
📊 **Accurate Backtesting** — Event-driven and vectorized engines for realistic results  
⚡ **Lightning Fast** — Optimized for speed and efficiency  
🔧 **Extensible** — Connect any exchange, broker, or data source  
📈 **Production Ready** — Built for real money trading

## Sponsors

<a href="https://www.finterion.com/" target="_blank">
    <picture style="height: 30px;">
    <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
    <img src="static/sponsors/finterion-light.png" alt="Finterion Logo" width="200px" height="50px">
    </picture>
</a>


## 🔌 Plugins & Integrations

Extend your trading bot with powerful plugins:

| Plugin | Description                                                                 |
|--------|-----------------------------------------------------------------------------|
| 🎯 **[PyIndicators](https://github.com/coding-kitties/PyIndicators)** | Technical analysis indicators for strategy development                      |
| 🏪 **[Finterion Plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin)** | Monetize & share your strategies with the public on Finterion's marketplace |

## 🌟 Powerful Features

| Feature | Description |
|---------|-------------|
| 🐍 **Python 3.10+** | Cross-platform support for Windows, macOS, and Linux |
| ⚙️ **Event-Driven Backtest** | Accurate, realistic backtesting with event-driven architecture |
| ⚡ **Vectorized Backtest** | Lightning-fast signal research and prototyping |
| 📊 **Advanced Metrics** | CAGR, Sharpe ratio, max drawdown, win rate, and 50+ more metrics |
| 📈 **Backtest Reports** | Generate detailed, comparison-ready reports |
| 🎯 **Statistical Testing** | Permutation testing for strategy significance evaluation |
| 💱 **Live Trading** | Real-time execution across multiple exchanges (via CCXT) |
| 💼 **Portfolio Management** | Full position and trade management with persistence |
| 📉 **Market Data** | OHLCV, tickers, custom data — Polars & Pandas native |
| 🔗 **Data Integrations** | PyIndicators, multiple data sources, custom providers |
| ☁️ **Cloud Deployment** | Azure Functions, AWS Lambda, and more |
| 🌐 **Web API** | REST API for bot interaction and monitoring |
| 🧩 **Fully Extensible** | Custom strategies, data providers, order executors |
| 🏗️ **Modular Design** | Build with reusable, composable components |



## 🚀 Quickstart

### 📦 Installation

Install the framework via [PyPI](https://pypi.org/project/investing-algorithm-framework/):

```bash
pip install investing-algorithm-framework
```

### 🎯 Initialize Your Project

Run the following command to scaffold a new trading bot:

```bash
investing-algorithm-framework init
```

For an AWS Lambda-ready project:

```bash
investing-algorithm-framework init --type aws_lambda
```

This creates:
- **app.py** — Your bot's entry point (keep as-is)
- **strategy.py** — Your trading strategy (customize this!)

> 💡 **Tip:** You can also create `default_web` or `azure_function` projects

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
    BacktestDateRange, BacktestReport, TakeProfitRule, StopLossRule


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
    take_profits = [
        TakeProfitRule(
            symbol="BTC",
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        ),
        TakeProfitRule(
            symbol="ETH",
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        )
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC",
            percentage_threshold=5,
            trailing=False,
            sell_percentage=100
        ),
        StopLossRule(
            symbol="ETH",
            percentage_threshold=5,
            trailing=False,
            sell_percentage=100
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

### Setup

Clone the repository and install dependencies using Poetry:

> Make sure you have [Poetry](https://python-poetry.org/docs/#installation) installed.

```bash
git clone https://github.com/coding-kitties/investing-algorithm-framework.git
cd investing-algorithm-framework
poetry install
```

### Running Tests

```bash
# Run all tests
python -m unittest discover -s tests

# Run specific test
python -m unittest tests.services.test_trade_service.TestTradeService
```

## ⚠️ Risk Disclaimer

🚨 **Use at Your Own Risk**

If you use this framework for your investments, **do not risk money which you are afraid to lose** until you have a clear understanding of how the framework works. 

**BEFORE YOU START USING MONEY WITH THE FRAMEWORK:**
- ✅ Test your strategies thoroughly with backtesting
- ✅ Review the source code of any plugins you use
- ✅ Start with small amounts on paper trading first
- ✅ Understand the risks involved

**We assume no responsibility for your investment results. The authors and all affiliates disclaim any liability for losses.**

---

## 🤝 Contributing

The investing algorithm framework is a **community-driven project**. We welcome contributions at all levels:

- 🐛 **Found a bug?** [Open an issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new)
- 💡 **Have an idea?** [Share it with us](https://github.com/coding-kitties/investing-algorithm-framework/issues/new)
- 🔧 **Want to code?** Check the [project board](https://github.com/coding-kitties/investing-algorithm-framework/projects?query=is%3Aopen)

**Guidelines:**
- Read the [Contributing Guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing%20Guide/contributing)
- Always create PRs against the `develop` branch, not `main`
- Open an issue before starting major feature work

---

## 📚 Documentation

Comprehensive documentation is available at [GitHub Pages](https://coding-kitties.github.io/investing-algorithm-framework/)

---

## 📬 Community

Join us and connect with other traders and developers:

* 💬 [Discord Community](https://discord.gg/dQsRmGZP) — Real-time chat and support
* 🔗 [Reddit Community](https://www.reddit.com/r/InvestingBots/) — Share strategies and discuss
* 📖 [Documentation](https://coding-kitties.github.io/investing-algorithm-framework/) — Guides and API references

---

## 🏆 Acknowledgements

We want to thank all contributors to this project. A full list can be found in [AUTHORS.md](https://github.com/coding-kitties/investing-algorithm-framework/blob/master/AUTHORS.md)

### Report Issues

If you discover a bug in the framework, please [search our issue tracker](https://github.com/coding-kitties/investing-algorithm-framework/issues?q=is%3Aissue) first. If it hasn't been reported, please [create a new issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new).

---

<div align="center">
  <p>
    <a href="https://github.com/coding-kitties/investing-algorithm-framework/stargazers">⭐ Star us on GitHub</a> · 
    <a href="https://discord.gg/dQsRmGZP">💬 Join Discord</a> · 
    <a href="https://github.com/coding-kitties/investing-algorithm-framework/issues/new">🐛 Report Bug</a>
  </p>
</div>
