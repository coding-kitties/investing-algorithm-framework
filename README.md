<h1 align="center">
    Investing Algorithm Framework
</h1>

<p align="center">
  <i align="center">Create trading strategies. Compare them side by side. Pick the best one. 🚀</i>
</p>

<h4 align="center">
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=master&label=tests&style=flat-square" alt="tests" style="height: 20px;">
  </a>
  <a href="https://pypi.org/project/investing-algorithm-framework/">
    <img src="https://img.shields.io/pypi/v/investing-algorithm-framework.svg?style=flat-square" alt="pypi" style="height: 20px;">
  </a>
  <a href="https://pepy.tech/project/investing-algorithm-framework">
    <img src="https://pepy.tech/badge/investing-algorithm-framework/month?style=flat-square" alt="downloads" style="height: 20px;">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/apache%202.0-blue.svg?style=flat-square&label=license" alt="license" style="height: 20px;">
  </a>
  <br>
  <a href="https://discord.gg/jQsnnYZgzR">
    <img src="https://img.shields.io/badge/discord-7289da.svg?style=flat-square&logo=discord" alt="discord" style="height: 20px;">
  </a>
  <a href="https://www.reddit.com/r/InvestingBots/">
    <img src="https://img.shields.io/badge/reddit-FF4500.svg?style=flat-square&logo=reddit&logoColor=white" alt="reddit" style="height: 20px;">
  </a>
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/stargazers">
    <img src="https://img.shields.io/github/stars/coding-kitties/investing-algorithm-framework?style=flat-square" alt="stars" style="height: 20px;">
  </a>
</h4>

<p align="center">
    <img src="static/showcase.svg" alt="dashboard" style="max-width: 100%;">
</p>

<p align="center">
  <a href="https://discord.gg/jQsnnYZgzR">
    <img src="https://img.shields.io/badge/Join%20our%20Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white" alt="Join our Discord">
  </a>
</p>

<p align="center">
  <sub><b>Sponsored by</b></sub>
  <br>
  <a href="https://www.finterion.com/" target="_blank">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
      <img src="static/sponsors/finterion-light.png" alt="Finterion" width="200">
    </picture>
  </a>
  <br>
  <sub>Marketplace for trading bots</sub>
</p>

## Introduction

`Investing Algorithm Framework` is a Python framework for creating, backtesting, and deploying trading strategies.

Most quant frameworks stop at "here's your backtest result." You get a number, maybe a chart, and then you're on your own figuring out which strategy is actually better.

This framework is built around the full loop: **create strategies → backtest them → compare them in a single report → deploy the winner.** It generates a self-contained HTML dashboard that lets you rank, filter, and visually compare every strategy you've tested — all in one view, no notebooks required.

<details open>
<summary>
 Features
</summary> <br>

- 📊 **30+ Metrics** — CAGR, Sharpe, Sortino, Calmar, VaR, CVaR, Max DD, Recovery & more
- ⚔️ **Multi-Strategy Comparison** — Rank, filter & compare strategies in a single interactive report
- 🪟 **Multi-Window Robustness** — Test across different time periods with window coverage analysis
- 📈 **Equity & Drawdown Charts** — Overlay equity curves, rolling Sharpe, drawdown & return distributions
- 🗓️ **Monthly Heatmaps & Yearly Returns** — Calendar heatmap per strategy with return/growth toggles
- 🎯 **Return Scenario Projections** — Good, average, bad & very bad year projections from backtest data
- 📉 **Benchmark Comparison** — Beat-rate analysis vs Buy & Hold, DCA, risk-free & custom benchmarks
- 📄 **One-Click HTML Report** — Self-contained file, no server, dark & light theme, shareable
- 🌐 **Load External Data** — Fetch CSV, JSON, or Parquet from any URL with caching and auto-refresh
- � **[Record Custom Variables](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/recording-variables)** — Track any indicator or metric during backtests with `context.record()`
- �🚀 **Build → Backtest → Deploy** — Local dev, cloud deploy (AWS / Azure), or monetize on Finterion

</details>

## Usage

To get started, install the framework and scaffold a new project:

```bash
pip install investing-algorithm-framework

# Generate project structure
investing-algorithm-framework init

# Or for cloud deployment
investing-algorithm-framework init --type aws_lambda
investing-algorithm-framework init --type azure_function
```

The [documentation](https://coding-kitties.github.io/investing-algorithm-framework/) provides guides and API reference. The [quick start](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation) will walk you through your first strategy.

<details>
<summary>
  Creating a Strategy
</summary> <br>

The framework is designed around the `TradingStrategy` class. You define **what data** your strategy needs and **when to buy or sell** — the framework handles execution, position management, and reporting.

```python
from typing import Dict, Any

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy, DataSource, TimeUnit, DataType,
    PositionSize, ScalingRule, StopLossRule,
)


class RSIEMACrossoverStrategy(TradingStrategy):
    """
    EMA crossover + RSI filter strategy with position scaling and stop losses.

    Buy when RSI is oversold AND a recent EMA crossover occurred.
    Sell when RSI is overbought AND a recent EMA crossunder occurred.
    Scale into winners, trail a stop loss, and let the framework handle the rest.
    """
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC", "ETH"]
    data_sources = [
        DataSource(
            identifier="BTC_ohlcv", symbol="BTC/EUR",
            data_type=DataType.OHLCV, time_frame="2h",
            market="BITVAVO", pandas=True, warmup_window=100,
        ),
        DataSource(
            identifier="ETH_ohlcv", symbol="ETH/EUR",
            data_type=DataType.OHLCV, time_frame="2h",
            market="BITVAVO", pandas=True, warmup_window=100,
        ),
    ]

    # Risk management
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20),
        PositionSize(symbol="ETH", percentage_of_portfolio=20),
    ]
    scaling_rules = [
        ScalingRule(
            symbol="BTC", max_entries=3,
            scale_in_percentage=[50, 25], cooldown_in_bars=5,
        ),
        ScalingRule(
            symbol="ETH", max_entries=3,
            scale_in_percentage=[50, 25], cooldown_in_bars=5,
        ),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5,
            sell_percentage=100, trailing=True,
        ),
        StopLossRule(
            symbol="ETH", percentage_threshold=5,
            sell_percentage=100, trailing=True,
        ),
    ]

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            df = data[f"{symbol}_ohlcv"]
            ema_short = ema(df, period=12, source_column="Close",
                           result_column="ema_short")
            ema_long = ema(ema_short, period=26, source_column="Close",
                          result_column="ema_long")
            ema_cross = crossover(ema_long,
                                  first_column="ema_short",
                                  second_column="ema_long",
                                  result_column="ema_crossover")
            rsi_data = rsi(df, period=14, source_column="Close",
                          result_column="rsi")

            rsi_oversold = rsi_data["rsi"] < 30
            recent_crossover = (
                ema_cross["ema_crossover"].rolling(window=10).max() > 0
            )
            signals[symbol] = (rsi_oversold & recent_crossover).fillna(False)

        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            df = data[f"{symbol}_ohlcv"]
            ema_short = ema(df, period=12, source_column="Close",
                           result_column="ema_short")
            ema_long = ema(ema_short, period=26, source_column="Close",
                          result_column="ema_long")
            ema_cross = crossunder(ema_long,
                                   first_column="ema_short",
                                   second_column="ema_long",
                                   result_column="ema_crossunder")
            rsi_data = rsi(df, period=14, source_column="Close",
                          result_column="rsi")

            rsi_overbought = rsi_data["rsi"] >= 70
            recent_crossunder = (
                ema_cross["ema_crossunder"].rolling(window=10).max() > 0
            )
            signals[symbol] = (rsi_overbought & recent_crossunder).fillna(False)

        return signals
```

Create as many strategy variants as you want — different parameters, different indicators, different symbols — then backtest them all and compare in a single report.

</details>

<details>
<summary>
  Backtest Report Dashboard
</summary> <br>

Every backtest produces a **single HTML file** you can open in any browser, share with teammates, or archive. No server, no dependencies, no Jupyter required.

```python
from investing_algorithm_framework import BacktestReport

# After running backtests
report = BacktestReport(backtest)
report.show()  # Opens dashboard in your browser

# Or load previously saved backtests from disk
report = BacktestReport.open(directory_path="path/to/backtests")
report.show()

# Compare multiple strategies side by side
report = BacktestReport.open(backtests=[backtest_a, backtest_b, backtest_c])
report.show()

# Save as a self-contained HTML file
report.save("my_report.html")
```

**Overview page** — KPI cards, key metrics ranking table, trading activity, return scenarios, equity curves, metric bar charts, monthly returns heatmap, return distributions, and window coverage matrix.

**Strategy pages** — Deep dive into each strategy with per-run equity curves, rolling Sharpe, drawdown, monthly/yearly returns, and portfolio summary.

</details>

<details open>
<summary>
 Capabilities
</summary> <br>

| | |
|---|---|
| **[Backtest Report Dashboard](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** | Self-contained HTML report with ranking tables, equity curves, metric charts, heatmaps, and strategy comparison |
| **[Event-Driven Backtesting](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtesting)** | Realistic, order-by-order simulation |
| **[Vectorized Backtesting](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/vector-backtesting)** | Fast signal research and prototyping |
| **50+ Metrics** | CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor, recovery factor, volatility, and more |
| **[Live Trading](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/application-setup)** | Connect to exchanges via CCXT for real-time execution |
| **[Portfolio Management](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/portfolio-configuration)** | Position tracking, trade management, persistence |
| **[Cloud Deployment](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment)** | Deploy to AWS Lambda, Azure Functions, or run as a web service |
| **[Market Data Providers](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-data-providers)** | Built-in providers for CCXT, Yahoo Finance, Alpha Vantage, and Polygon — or build your own |
| **[Load External Data](https://coding-kitties.github.io/investing-algorithm-framework/Data/external-data)** | Fetch CSV, JSON, or Parquet from any URL with caching, date parsing, and pre/post-processing |
| **[Strategies](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/strategies)** | OHLCV, tickers, custom data — Polars and Pandas native |
| **[Extensible](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-data-providers)** | Custom data providers, order executors, and strategy classes |

</details>

## Plugins

| Plugin | Description |
|--------|-------------|
| [PyIndicators](https://github.com/coding-kitties/PyIndicators) | Technical analysis indicators (EMA, RSI, MACD, etc.) |
| [Finterion Plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin) | Share and monetize strategies on Finterion's marketplace |

## Development

```bash
git clone https://github.com/coding-kitties/investing-algorithm-framework.git
cd investing-algorithm-framework
poetry install

# Run all tests
python -m unittest discover -s tests
```

## Resources

- **[Documentation](https://coding-kitties.github.io/investing-algorithm-framework/)** — Guides and API reference
- **[Quick Start](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation)** — Get up and running
- **[Discord](https://discord.gg/dQsRmGZP)** — Chat and support
- **[Reddit](https://www.reddit.com/r/InvestingBots/)** — Strategy discussion

## Contributing

- [Open an issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new) for bugs or ideas
- Read the [Contributing Guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing%20Guide/contributing)
- PRs go against the `develop` branch

## Risk Disclaimer

If you use this framework for real trading, **do not risk money you are afraid to lose.** Test thoroughly with backtesting first. Start small. We assume no responsibility for your investment results.

## Acknowledgements

We want to thank all contributors to this project. A full list can be found in [AUTHORS.md](https://github.com/coding-kitties/investing-algorithm-framework/blob/master/AUTHORS.md).

## Sponsor

<a href="https://www.finterion.com/" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png"><source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png"><img src="static/sponsors/finterion-light.png" alt="Finterion" width="180"></picture></a>

**[Finterion](https://www.finterion.com/)** — Marketplace for trading bots. Monetize your strategies by publishing them on Finterion.
