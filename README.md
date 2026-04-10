<div align="center">
  <h1>Investing Algorithm Framework</h1>

  <p style="font-size: 18px; font-weight: 600; margin: 15px 0;">
    Create trading strategies. Compare them side by side. Pick the best one.
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

  > ⭐ **If you like this project, please consider [starring](https://github.com/coding-kitties/investing-algorithm-framework) it!**

  <br>

  <table>
    <tbody>
      <tr>
        <td align="center" style="border: none;">
          <sub><b>Sponsored by</b></sub>
          <br><br>
          <a href="https://www.finterion.com/" target="_blank">
            <picture>
              <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
              <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
              <img src="static/sponsors/finterion-light.png" alt="Finterion" width="180">
            </picture>
          </a>
          <br>
          <sub>Marketplace for trading bots</sub>
        </td>
      </tr>
    </tbody>
  </table>

</div>

---

## Why This Framework?

Most quant frameworks stop at "here's your backtest result." You get a number, maybe a chart, and then you're on your own figuring out which strategy is actually better.

**Investing Algorithm Framework** is built around the full loop: **create strategies → backtest them → compare them in a single report → deploy the winner.**

The framework generates a **self-contained HTML dashboard** that lets you rank, filter, and visually compare every strategy you've tested — all in one view, no notebooks required.

---

## The Backtest Report Dashboard

Every backtest produces a **single HTML file** you can open in any browser, share with teammates, or archive. No server, no dependencies, no Jupyter required.

### Overview Page — See All Strategies at a Glance

- **KPI cards** — Portfolio value, total return, best CAGR, best Sharpe, lowest max drawdown across all strategies
- **Key Metrics ranking table** — CAGR, Sharpe, Sortino, max drawdown, volatility, recovery factor — sortable, with the best value in each column highlighted
- **Trading Activity ranking table** — Total trades, win rate, profit factor, avg win/loss duration, trades per year/month/week
- **Return Scenarios table** — Projected returns for good, average, bad, and very bad years based on historical performance
- **Equity curve chart** — Overlay all strategy equity curves on a single chart; click any strategy to toggle it on/off
- **Metric bar charts** — Side-by-side comparison of CAGR, Sharpe, max drawdown, win rate, and more
- **Monthly returns heatmap** — Per-strategy calendar heatmap of monthly returns, with year filter
- **Return/growth distribution** — Monthly and yearly return histograms for each strategy
- **Window coverage matrix** — See which strategies cover which backtest time windows, with comparability stats

### Compare Page — Deep Dive into Selected Strategies

- **Strategy selection modal** — Click to pick which strategies to compare; sort by any metric, paginate large sets
- **Filtered equity curves** — Only the selected strategies are shown
- **Filtered metric charts** — Bar charts update to reflect your selection
- **Filtered ranking tables** — Key Metrics, Trading Activity, and Return Scenarios tables all respect your selection
- **Collapsible cards** — Collapse any section to focus on what matters

### How It Works

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

# Recalculate metrics after framework updates
from investing_algorithm_framework import recalculate_backtests
recalculate_backtests(report.backtests)
report.show()
```

---

## Creating Strategies

The framework is designed around the `TradingStrategy` class. You define **what data** your strategy needs and **when to buy or sell** — the framework handles execution, position management, and reporting.

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, Context, OrderSide
)

class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbol_pairs = ["BTC/EUR"]

    def apply_strategy(self, context: Context, market_data):
        for pair in self.symbol_pairs:
            symbol = pair.split("/")[0]
            ohlcv = market_data[f"{pair}-ohlcv-2h"]
            price = ohlcv["Close"].iloc[-1]

            # Your buy/sell logic here
            if self.should_buy(ohlcv) and not context.has_position(symbol):
                context.create_limit_order(
                    target_symbol=symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                )

            if self.should_sell(ohlcv) and context.has_position(symbol):
                context.create_limit_order(
                    target_symbol=symbol,
                    order_side=OrderSide.SELL,
                    price=price,
                    percentage_of_portfolio=100,
                )
```

Create as many strategy variants as you want — different parameters, different indicators, different symbols — then backtest them all and compare in a single report.

### Scaffold a New Project

```bash
pip install investing-algorithm-framework

# Generate project structure
investing-algorithm-framework init

# Or for cloud deployment
investing-algorithm-framework init --type aws_lambda
investing-algorithm-framework init --type azure_function
```

This creates an `app.py` entry point and a `strategy.py` file you can start editing immediately.

---

## Features

| | |
|---|---|
| **Backtest Report Dashboard** | Self-contained HTML report with ranking tables, equity curves, metric charts, heatmaps, and strategy comparison |
| **Event-Driven Backtesting** | Realistic, order-by-order simulation |
| **Vectorized Backtesting** | Fast signal research and prototyping |
| **50+ Metrics** | CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor, recovery factor, volatility, and more |
| **Live Trading** | Connect to exchanges via CCXT for real-time execution |
| **Portfolio Management** | Position tracking, trade management, persistence |
| **Cloud Deployment** | Deploy to AWS Lambda, Azure Functions, or run as a web service |
| **Market Data** | OHLCV, tickers, custom data — Polars and Pandas native |
| **Extensible** | Custom data providers, order executors, and strategy classes |

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

## Risk Disclaimer

If you use this framework for real trading, **do not risk money you are afraid to lose.** Test thoroughly with backtesting first. Start small. We assume no responsibility for your investment results.

---

## Contributing

- [Open an issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new) for bugs or ideas
- Read the [Contributing Guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing%20Guide/contributing)
- PRs go against the `develop` branch

## Community

* [Discord](https://discord.gg/dQsRmGZP) — Chat and support
* [Reddit](https://www.reddit.com/r/InvestingBots/) — Strategy discussion
* [Documentation](https://coding-kitties.github.io/investing-algorithm-framework/) — Guides and API reference

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
