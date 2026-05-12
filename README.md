<h1 align="center">
    Investing Algorithm Framework
</h1>

<p align="center">
  <i align="center">Create trading strategies. Compare them side by side. Pick the best one and Deploy 🚀</i>
</p>

<h4 align="center">
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=linux&style=flat-square&logo=linux&logoColor=white" alt="linux main" style="height: 20px;">
  </a>
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=macos&style=flat-square&logo=apple&logoColor=white" alt="macos main" style="height: 20px;">
  </a>
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=windows&style=flat-square&logo=windows&logoColor=white" alt="windows main" style="height: 20px;">
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
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/hero-light.svg">
    <img src="static/features/hero-dark.svg" alt="Investing Algorithm Framework — features overview" style="max-width: 100%;">
  </picture>
</p>

<p align="center">
  <a href="https://discord.gg/jQsnnYZgzR">
    <img src="https://img.shields.io/badge/Join%20our%20Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white" alt="Join our Discord">
  </a>
</p>

<p align="center">
  <sub>Proudly sponsored by</sub>
  <br>
  <a href="https://www.finterion.com/" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png"><source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png"><img src="static/sponsors/finterion-light.png" alt="Finterion" width="180"></picture></a>
</p>

## Introduction

`Investing Algorithm Framework` is a Python framework for creating, backtesting, and deploying trading strategies.

Most quant frameworks stop at "here's your backtest result." You get a number, maybe a chart, and then you're on your own figuring out which strategy is actually better.

This framework is built around the full loop: **create strategies → vector backtest for signals analysis → compare them in a single report → event backtest the most promising strategies → deploy the winner.** It generates a self-contained HTML dashboard that lets you rank, filter, and visually compare every strategy you've tested — all in one view, no notebooks required.

<details open>
<summary>
 Features
</summary> <br>

- 📊 **[30+ Metrics](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/metrics)** — CAGR, Sharpe, Sortino, Calmar, VaR, CVaR, Max DD, Recovery & more
- 🧮 **[Cross-Sectional Pipelines](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines)** — Rank, filter and score entire universes of symbols every iteration with a tidy factor table
- ⚡ **[Vector Backtesting for Signal Analysis](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/vector-backtesting)** — Quickly test your strategy logic on historical data to see how signals would have behaved before committing to full event-driven backtests
- 🏃 **[Event-Driven Backtesting](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/event-backtesting)** — Once promising strategies are identified via vector backtests, run full event-driven backtests to simulate realistic execution and portfolio management
- 🔀 **[Permutation Testing / Monte Carlo Simulations](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Assess the statistical robustness of your strategies by running them across randomized market scenarios to see how often your results could occur by chance
- 🚀 **[Deployment](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment)** — Once the best strategy is identified through backtesting and comparison, deploy it to production locally or in the cloud (AWS Lambda / Azure Functions) to start live trading
- ⚔️ **[Multi-Strategy Comparison](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Rank, filter & compare strategies in a single interactive report
- 🪟 **[Multi-Window Robustness](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Test across different time periods with window coverage analysis
- 📈 **[Equity & Drawdown Charts](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Overlay equity curves, rolling Sharpe, drawdown & return distributions
- 🗓️ **[Monthly Heatmaps & Yearly Returns](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Calendar heatmap per strategy with return/growth toggles
- 🎯 **[Return Scenario Projections](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Good, average, bad & very bad year projections from backtest data
- 📉 **[Benchmark Comparison](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Beat-rate analysis vs Buy & Hold, DCA, risk-free & custom benchmarks
- 📄 **[One-Click HTML Report](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)** — Self-contained file, no server, dark & light theme, shareable
- 📦 **[Custom `.iafbt` Backtest Bundle Format](https://coding-kitties.github.io/investing-algorithm-framework/Data/backtest_data)** — An explicit, versioned, compressed, language-portable container (zstd + msgpack with magic-byte header) plus a separate parquet index for fast filtering without loading. ~21× smaller and ~27× fewer files than standard filebased directory layouts, with parallel I/O for fast load/save of large amounts of backtests.
- 🗄️ **[Tiered Backtest Storage Layer](examples/storage_layer_demo/README.md)** — Manage thousands of `.iafbt` bundles with a Tier-1 SQLite index (sub-100 ms ranks/filters over 10k+ backtests), a swappable `BacktestStore` protocol (`LocalDirStore`, `LocalTieredStore`), content-addressed Tier-3 OHLCV deduplication, and a CLI (`iaf index` / `iaf list` / `iaf rank` / `iaf migrate-store`) that plugs straight into the HTML dashboard.
- 🌐 **[Load External Data](https://coding-kitties.github.io/investing-algorithm-framework/Data/external-data)** — Fetch CSV, JSON, or Parquet from any URL with caching and auto-refresh
- � **[Per-Market Deposit Schedules & Portfolio Sync](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/portfolio-sync)** — Declare recurring or one-shot external cash flows on a market with `deposit_schedule=` / `auto_sync=True`. Backtests simulate the deposits; live mode reconciles with the broker — same `context.sync_portfolio()` API in both modes.
- �📝 **[Record Custom Variables](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/recording-variables)** — Track any indicator or metric during backtests with `context.record()`
- 🚀 **[Build → Backtest → Deploy](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/application-setup)** — Local dev, cloud deploy (AWS / Azure), or monetize on Finterion

</details>

<details open>
<summary>
  <strong>Backtesting Engines</strong>
</summary> <br>

### ⚡ Vector Backtesting — Test thousands of strategies, fast

Polars-powered vectorized signal evaluation. Compare thousands of strategies side by side, sweep parameter grids, run multi-window robustness checks, rank by key metrics and surface your top candidates in seconds — all before committing to a full event-driven simulation.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/vector-backtest-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/vector-backtest-light.svg">
    <img src="static/features/vector-backtest-dark.svg" alt="Vector backtest engine — run thousands of strategies in parallel" style="max-width: 100%;">
  </picture>
</p>

### 🏃 Event-Driven Backtesting — Bar-by-bar realism

Once you've narrowed down promising strategies, run them through a full event-driven simulation. Pluggable slippage and fill models, partial fills, and a complete simulation blotter — using the **same code path** you'll deploy live.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/event-backtest-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/event-backtest-light.svg">
    <img src="static/features/event-backtest-dark.svg" alt="Event-driven backtest engine — bar-by-bar realism with order fills" style="max-width: 100%;">
  </picture>
</p>

</details>

<details open>
<summary>
  <strong>Backtest Analysis & Dashboard</strong>
</summary> <br>

Every backtest produces a **self-contained HTML dashboard** — open it in any browser, share with teammates, archive it. No server, no Jupyter, no dependencies. Compare strategies side-by-side, drill into trades, and capture your reasoning as you go.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/dashboard-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/dashboard-light.svg">
    <img src="static/features/dashboard-dark.svg" alt="Backtest analysis dashboard with MCP server and notes" style="max-width: 100%;">
  </picture>
</p>

- **Self-contained HTML reports** — equity curves, drawdowns, trade lists, monthly returns, side-by-side strategy comparison
- **Built-in MCP server** — let Copilot, Claude, or any MCP-compatible agent query your backtests, rank strategies, and reason over trades through `investing-algorithm-framework mcp`
- **Notes keeping** — annotate every backtest with hypotheses, observations and conclusions; notes travel with the report so your research is never lost

#### From backtest results to a report

Every backtest API — vector or event-driven — returns the same `Backtest` object, which the `BacktestReport` consumes directly. So whether you're iterating over an in-memory list or a folder of persisted `.iafbt` bundles, the path to the dashboard is the same:

```python
from investing_algorithm_framework import BacktestReport

# --- Single event-driven backtest ---
backtest = app.run_backtest(backtest_date_range=date_range)
BacktestReport(backtests=[backtest]).save("event_report.html")

# --- A sweep of vector backtests (parameter grid / multi-window) ---
backtests = app.run_vector_backtests(
    strategies=[StrategyA(), StrategyB(), StrategyC()],
    backtest_date_ranges=[range_2022, range_2023, range_2024],
    n_workers=-1,
    backtest_storage_directory="./my-backtests/",  # persists .iafbt bundles
    show_progress=True,
)
BacktestReport(backtests=backtests).save("sweep_report.html")

# --- Or: load a folder of bundles back later (parallel decode) ---
report = BacktestReport.open(
    directory_path="./my-backtests/",
    workers=-1,
    show_progress=True,
)
report.save("from_disk_report.html")
```

For sweeps that grow into the thousands, combine this with the [Backtest Storage Layer](examples/storage_layer_demo/README.md) below — rank in SQLite first, then load only the winners into the report:

```python
from investing_algorithm_framework import BacktestReport
from investing_algorithm_framework.cli.index_command import (
    build_index, rank_index,
)
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)

# 1. Build (or refresh) the Tier-1 SQLite index over the folder of bundles.
build_index("./my-backtests/")

# 2. Pick the top 25 by Sharpe straight from SQLite — no Parquet decoded.
top = rank_index(
    "./my-backtests/",
    by="sharpe_ratio",
    where="summary_number_of_trades > 50",
    limit=25,
)

# 3. Materialise only those 25 bundles through the BacktestStore protocol.
store = LocalDirStore("./my-backtests/")
winners = [store.open(row["bundle_path"]) for row in top]

# 4. Render a focused dashboard with just the winners.
BacktestReport(backtests=winners).save("top25_by_sharpe.html")
```

> 💡 **Going further than a single HTML file?** A self-contained `report.html` is great for sharing a hand-picked set of winners, but past a few dozen backtests in one document the browser starts to struggle. For team-scale workflows — searching, filtering, comparing and annotating across thousands of backtests in a server-backed UI — use a quant infrastructure provider such as **[Finterion](https://www.finterion.com/)**, which is purpose-built on top of this storage layer for large-scale backtest analysis.

→ [Backtest dashboard docs](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtesting) · [MCP server docs](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/mcp-server)

</details>

<details open>
<summary>
  <strong>Backtest Storage Layer — scale to thousands of backtests</strong>
</summary> <br>

Once you start sweeping parameter grids and walk-forward windows, a flat folder of `.iafbt` bundles stops scaling: every comparison re-decodes multi-MB Parquet metric blobs just to read a Sharpe number. The storage layer fixes that with three tiers behind a single `BacktestStore` protocol:

- **Tier-1 — SQLite index (`index.sqlite`)**: one row per bundle with every scalar from `BacktestSummaryMetrics` promoted to its own column. Ranking 10k+ bundles becomes a sub-100 ms SQL query — no `.iafbt` is opened.
- **Tier-2 — `BacktestStore` adapters**: `LocalDirStore` (flat folder of bundles) or `LocalTieredStore` (hive-partitioned layout). Same handle-based API, swap the implementation without touching call sites.
- **Tier-3 — content-addressed OHLCV chunks**: SHA-256 deduped per-symbol OHLCV blobs shared across every bundle that references them. `garbage_collect_ohlcv()` reclaims orphans.

A CLI ties it all together: `iaf index` builds/refreshes the Tier-1 SQLite, `iaf list` / `iaf rank` query it, and `iaf migrate-store` moves a whole collection between store kinds in one command.

#### Typical workflow

```python
from investing_algorithm_framework import BacktestReport
from investing_algorithm_framework.cli.index_command import (
    build_index, rank_index,
)
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)

# 1. Build (or refresh) the Tier-1 SQLite index over a folder of .iafbt bundles.
build_index("./my-backtests/")          # equivalent to: iaf index ./my-backtests/

# 2. Pick the top 20 by Sharpe straight from SQLite — no Parquet decoded.
top = rank_index(
    "./my-backtests/",
    by="sharpe_ratio",
    where="summary_number_of_trades > 50",
    limit=20,
)

# 3. Materialise just those 20 bundles through the BacktestStore protocol.
store = LocalDirStore("./my-backtests/")
backtests = [store.open(row["bundle_path"]) for row in top]

# 4. Feed them straight into the HTML dashboard.
BacktestReport(backtests=backtests).save("top20.html")
```

Or from the shell:

```bash
iaf index ./my-backtests/
iaf rank  ./my-backtests/ --by sharpe_ratio --where "summary_number_of_trades > 50" -n 20
iaf list  ./my-backtests/ --sort calmar_ratio --json
iaf migrate-store --from local-dir --src ./my-backtests/ \
                  --to   local-tiered --dst ./tiered/
```

→ End-to-end runnable example: [`examples/storage_layer_demo/`](examples/storage_layer_demo/README.md)

</details>

<details open>
<summary>
  <strong>Live Trading</strong>
</summary> <br>

Once a strategy proves itself in backtests, deploy it with the **same code path** you backtested. Connect to any exchange — use the built-in [CCXT](https://github.com/ccxt/ccxt) integration, or plug in your own [`OrderExecutor`](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-order-executors) for brokers, FIX gateways, or any custom venue. Run locally, in Docker, or deploy serverless to **AWS Lambda** or **Azure Functions**. Built-in portfolio tracking, position management, order persistence, and automatic state recovery.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/live-trading-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/live-trading-light.svg">
    <img src="static/features/live-trading-dark.svg" alt="Live trading & deployment — AWS Lambda and Azure Functions" style="max-width: 100%;">
  </picture>
</p>

- **No code rewrites** — your `TradingStrategy` runs identically in backtest, paper trading and live
- **Cloud deploy** — `investing-algorithm-framework init --type aws_lambda` / `--type azure_function`
- **Multiple exchanges & venues** — CCXT integration out of the box (Binance, Bitvavo, Coinbase, Kraken …), or plug in your own `OrderExecutor` for any broker / FIX / custom venue
- **Portfolio persistence** — trades, orders and positions survive restarts

→ [Live trading & deployment docs](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment)

</details>

<details open>
<summary>
  <strong>Marketplace Integration</strong>
</summary> <br>

Publish your winning strategies to the [**Finterion**](https://www.finterion.com/) marketplace and monetize them. Investors subscribe to your bot, you earn a recurring revenue share — the framework handles the technical integration.

<p align="center">
  <a href="https://www.finterion.com/" target="_blank">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="static/features/marketplace-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="static/features/marketplace-light.svg">
      <img src="static/features/marketplace-dark.svg" alt="Marketplace integration — featuring Finterion" style="max-width: 100%;">
    </picture>
  </a>
</p>

→ [Finterion plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin)

</details>

<details>
<summary>
  <strong>Usage and Installation</strong>
</summary> <br>

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

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/dashboard-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/dashboard-light.svg">
    <img src="static/features/dashboard-dark.svg" alt="Self-contained HTML backtest dashboard" style="max-width: 100%;">
  </picture>
</p>

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
| **[Cross-Sectional Pipelines](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines)** | Compute factors across many symbols at once — rank, filter and score universes per iteration |
| **50+ Metrics** | CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor, recovery factor, volatility, and more |
| **[Live Trading](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/application-setup)** | Connect to exchanges via CCXT for real-time execution |
| **[Portfolio Management](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/portfolio-configuration)** | Position tracking, trade management, persistence |
| **[Cloud Deployment](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment)** | Deploy to AWS Lambda, Azure Functions, or run as a web service |
| **[Market Data Providers](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-data-providers)** | Built-in providers for CCXT, Yahoo Finance, Alpha Vantage, and Polygon — or build your own |
| **[Load External Data](https://coding-kitties.github.io/investing-algorithm-framework/Data/external-data)** | Fetch CSV, JSON, or Parquet from any URL with caching, date parsing, and pre/post-processing |
| **[Record Custom Variables](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/recording-variables)** | Track any indicator or metric during backtests with `context.record()` |
| **[Strategies](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/strategies)** | OHLCV, tickers, custom data — Polars and Pandas native |
| **[Extensible](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-data-providers)** | Custom data providers, order executors, and strategy classes |

</details>

</details>

<details>
<summary>
  <strong>Plugins</strong>
</summary> <br>

| Plugin | Description |
|--------|-------------|
| [PyIndicators](https://github.com/coding-kitties/PyIndicators) | Technical analysis indicators (EMA, RSI, MACD, etc.) |
| [Finterion Plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin) | Share and monetize strategies on Finterion's marketplace |

</details>

## Development & Contributing

We welcome contributions! Open an issue, pick one up, or send a PR.

```bash
git clone https://github.com/coding-kitties/investing-algorithm-framework.git
cd investing-algorithm-framework
poetry install

# Run all tests
python -m unittest discover -s tests
```

- [Open an issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new) for bugs or ideas
- Read the [Contributing Guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing%20Guide/contributing)
- PRs go against the `dev` branch

## Resources

- **[Documentation](https://coding-kitties.github.io/investing-algorithm-framework/)** — Guides and API reference
- **[Quick Start](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation)** — Get up and running
- **[Discord](https://discord.gg/dQsRmGZP)** — Chat and support
- **[Reddit](https://www.reddit.com/r/InvestingBots/)** — Strategy discussion

## Risk Disclaimer

If you use this framework for real trading, **do not risk money you are afraid to lose.** Test thoroughly with backtesting first. Start small. We assume no responsibility for your investment results.

## Acknowledgements

We want to thank all contributors to this project. A full list can be found in [AUTHORS.md](https://github.com/coding-kitties/investing-algorithm-framework/blob/master/AUTHORS.md).

## Sponsor

<a href="https://www.finterion.com/" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png"><source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png"><img src="static/sponsors/finterion-light.png" alt="Finterion" width="180"></picture></a>

**[Finterion](https://www.finterion.com/)** — Marketplace for trading bots. Monetize your strategies by publishing them on Finterion.
