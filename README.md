<h1 align="center">
  Investing Algorithm Framework
</h1>

<p align="center">
  <i>Build strategies, backtest at scale, compare results, and deploy the winner without rewriting your strategy.</i>
</p>

<h4 align="center">
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain"><img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=linux&style=flat-square&logo=linux&logoColor=white" alt="Linux build"></a>
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain"><img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=macos&style=flat-square&logo=apple&logoColor=white" alt="macOS build"></a>
  <a href="https://github.com/coding-kitties/investing-algorithm-framework/actions/workflows/test.yml?query=branch%3Amain"><img src="https://img.shields.io/github/actions/workflow/status/coding-kitties/investing-algorithm-framework/test.yml?branch=main&label=windows&style=flat-square&logo=windows&logoColor=white" alt="Windows build"></a>
  <a href="https://pypi.org/project/investing-algorithm-framework/"><img src="https://img.shields.io/pypi/v/investing-algorithm-framework.svg?style=flat-square" alt="PyPI version"></a>
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/apache%202.0-blue.svg?style=flat-square&label=license" alt="Apache 2.0 license"></a>
  <a href="https://finterion.com/community/forum"><img src="https://finterion.com/api/forum-badge.svg" alt="Finterion forum" height="20"></a>
</h4>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/hero-light.svg">
    <img src="static/features/hero-dark.svg" alt="Investing Algorithm Framework features overview" style="max-width: 100%;">
  </picture>
</p>

Investing Algorithm Framework is a Python framework for the complete quantitative
trading workflow. Define a strategy once, explore it with vector backtests,
validate it in an event-driven simulation, inspect the results in an interactive
dashboard, and run the same strategy in paper or live trading.

> **v9.0.0 alpha is available.** Install the prerelease explicitly:
>
> ```bash
> pip install investing-algorithm-framework==9.0.0a18
> ```
>
> See the [v9.0 release notes](docusaurus/blog/2026-08-02-v9.0-release.md)
> and [changelog](CHANGELOG.md). The APIs below describe current v9 development.

### Feature Highlights

- 🔁 **[Long and short trading](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/orders):** Define entry and exit signals once and run the same strategy in vector backtests, event-driven backtests, paper trading, and live trading.
- ⚡ **[Vector backtesting](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/vector-backtesting):** Evaluate signals and sweep thousands of strategy variants quickly with Polars-powered execution.
- 🏃 **[Event-driven backtesting](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/event-backtesting):** Validate candidates bar by bar with realistic orders, fills, costs, and portfolio management.
- 🪟 **[Studies, universes, and backtest windows](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/studies):** Define the assets, assumptions, and rolling, anchored, holdout, walk-forward, time-OOS, or universe-OOS periods for each experiment.
- 🗂️ **[Open Backtest Format](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/open-backtest-format):** Keep complete vector and event results in portable, versioned `.obtf` bundles.
- 🗄️ **[Tiered storage and indexing](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-storage):** Rank and filter 10,000+ backtests through SQLite without decoding full result bundles.
- 📊 **[80+ performance metrics](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/metrics):** Analyze CAGR, Sharpe, Sortino, Calmar, VaR/CVaR, drawdown, recovery, and benchmark-relative returns.
- 📈 **[Interactive dashboard](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports):** Compare strategies, inspect trades and charts, review window coverage, and save a self-contained HTML report.
- 🔀 **[Monte Carlo testing](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/permutation-testing):** Measure how often randomized market paths match or outperform a strategy's observed results.
- 🧮 **[Cross-sectional pipelines](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines):** Rank, filter, and score entire universes of symbols during each strategy iteration.
- 🧠 **[Confluence scoring cards](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/confluence-cards):** Build explainable decisions from requirements, weighted evidence, vetoes, and score thresholds.
- 🛡️ **[Declarative risk rules](https://coding-kitties.github.io/investing-algorithm-framework/Risk%20Rules/overview):** Configure sizing, exposure limits, scaling, stop losses, take profits, and signal cooldowns.
- 💸 **[Execution cost models](https://coding-kitties.github.io/investing-algorithm-framework/Risk%20Rules/trading-cost):** Apply percentage, fixed, basis-point, or volume-aware commission and slippage assumptions.
- 🔐 **[Portfolio and credentials management](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/portfolio-configuration):** Configure markets, balances, fees, paper trading, and environment-based credentials without hardcoding secrets.
- 🚀 **[Flexible deployment](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment):** Run locally, self-host, deploy to AWS Lambda or Azure Functions, or publish through Finterion.
- 🌐 **[Extensible integrations](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/custom-data-providers):** Add custom data providers, order executors, storage adapters, metrics, strategies, and optimizers.
- 🤖 **[Built-in MCP server](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/mcp-server):** Let compatible AI tools query backtests, compare strategies, inspect trades, and manage research notes.
- ↔️ **[Position modes: NETTING vs. HEDGE](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/position-modes):** Choose one net direction per symbol or maintain independent long and short legs with separate risk controls and P&L.

<a id="strategy-definition"></a>
<details>
<summary><strong>Strategy Definition</strong></summary>
<br>

Strategies are `TradingStrategy` subclasses that declare their data, schedule,
signal logic, and risk rules. The framework handles data loading, order execution,
position management, persistence, and reporting around them.

```python
from pyindicators import crossover, crossunder, ema, rsi

from investing_algorithm_framework import ConfluenceCard, CooldownRule, \
    DataSource, DataType, EvidenceGroup, ExposureRule, Operator, \
    PrimaryGroup, ScalingRule, Schedule, ScoreRule, SignalSide, \
    StopLossRule, TakeProfitRule, TimeUnit, TradingStrategy, \
    condition, PositionSize


def create_confluence_card(name, rsi_operator, rsi_value, cross_column):
  return ConfluenceCard(
    name=name,
    primary=PrimaryGroup(name="RSI reversal", rules=(ScoreRule(
      name=f"RSI {rsi_operator.value} {rsi_value}",
      expression=condition("rsi", rsi_operator, value=rsi_value), points=3,
    ),), minimum_matches=1),
    secondary=(EvidenceGroup(name="EMA confirmation", rules=(ScoreRule(
      name="Recent EMA cross",
      expression=condition(cross_column, Operator.GT, value=0), points=2,
    ),), minimum_score=2),),
    minimum_score=5,
  )


class RSIEMACrossoverStrategy(TradingStrategy):
  schedule = Schedule.every(2, TimeUnit.HOUR)
  symbols = ["BTC"]
  data_sources = [DataSource(
    identifier="BTC_ohlcv", symbol="BTC/EUR", data_type=DataType.OHLCV,
    time_frame="2h", market="BITVAVO", pandas=True, warmup_window=100,
  )]

  # Portfolio and position risk controls.
  exposure_rule = ExposureRule(max_portfolio_percentage=80)
  position_sizes = [PositionSize(symbol="BTC", percentage_of_portfolio=20)]
  scaling_rules = [ScalingRule(
    symbol="BTC", max_entries=3, scale_in_percentage=[50, 25],
    cooldown_in_bars=5,
  )]
  stop_losses = [StopLossRule(
    symbol="BTC", percentage_threshold=5, sell_percentage=100, trailing=True,
  )]
  take_profits = [TakeProfitRule(
    symbol="BTC", percentage_threshold=10, sell_percentage=50,
  )]
  cooldowns = [
    CooldownRule(symbol="BTC", trigger="sell", blocks="buy", bars=12),
    CooldownRule(trigger="any", blocks="any", bars=2),
  ]

  # Weighted, explainable entry and exit decisions.
  signal_cards = {
    SignalSide.OPEN_LONG: create_confluence_card(
      "Open long", Operator.LT, 30, "recent_crossover"),
    SignalSide.CLOSE_LONG: create_confluence_card(
      "Close long", Operator.GTE, 70, "recent_crossunder"),
    SignalSide.OPEN_SHORT: create_confluence_card(
      "Open short", Operator.GTE, 70, "recent_crossunder"),
    SignalSide.CLOSE_SHORT: create_confluence_card(
      "Close short", Operator.LT, 30, "recent_crossover"),
  }

  def prepare_signal_data(self, data):
    """Prepare the same card inputs for every execution mode."""
    frame = data["BTC_ohlcv"].copy()
    frame = ema(frame, "Close", 12, "ema_short")
    frame = ema(frame, "Close", 26, "ema_long")
    frame = crossover(frame, "ema_short", "ema_long", "ema_crossover")
    frame = crossunder(frame, "ema_short", "ema_long", "ema_crossunder")
    frame = rsi(frame, "Close", 14, "rsi")
    frame["recent_crossover"] = frame["ema_crossover"].rolling(10).max()
    frame["recent_crossunder"] = frame["ema_crossunder"].rolling(10).max()
    return {"BTC": frame}
```

The framework evaluates `signal_cards` against the prepared columns and creates
signals and decision traces automatically. `prepare_signal_data` is shared by
vector backtests, event-driven backtests, paper trading, and live trading, while
the declarative rules govern sizing, exposure, scaling, exits, and cooldowns in
each mode. The four cards cover long entry and exit plus short entry and cover.

Fees and slippage belong to the portfolio or backtest study because they describe
a venue or scenario rather than signal logic.

See the [strategy guide](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/strategies),
the [basic example](docusaurus/docs/Getting%20Started/strategies.md#basic-strategy-structure),
and the [strategy showcase](examples/algorithm_examples/strategies_showcase/README.md).

</details>

<a id="backtesting"></a>
<details>
<summary><strong>Backtesting</strong></summary>
<br>

Backtests use a `Study` to describe the experiment and a
`BacktestRunConfiguration` to control execution and persistence.

```python
from investing_algorithm_framework import BacktestRunConfiguration

results = app.run_backtests(
    strategies=strategies,
    study=training_study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./my-backtests",
        n_workers=8,
        memory_budget_mb=16_384,
        min_available_memory_mb=4_096,
    ),
)

print(results.df)
```

Both engines return a disk-backed `BacktestIndex`. Use the index for scalar
filtering and ranking, then load selected full results with
`results.iter_backtests()` or `results.load_backtests()`.

### Vector Backtesting

The Polars-powered vector engine evaluates signal series in bulk. Use it for
rapid signal research, parameter sweeps, large candidate sets, and early-stage
filtering before running more expensive simulations.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/vector-backtest-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/vector-backtest-light.svg">
    <img src="static/features/vector-backtest-dark.svg" alt="Vector backtest engine" style="max-width: 100%;">
  </picture>
</p>

### Event-Driven Backtesting

The event engine processes market data bar by bar through the same strategy and
order path used in live trading. Use it to validate execution behavior, fills,
costs, portfolio changes, and interactions between strategies.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/event-backtest-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/event-backtest-light.svg">
    <img src="static/features/event-backtest-dark.svg" alt="Event-driven backtest engine" style="max-width: 100%;">
  </picture>
</p>

### Robustness Studies

`Study`, `Universe`, and `BacktestWindow` support single-window tests, rolling
windows, anchored windows, holdouts, walk-forward k-fold validation, and
out-of-sample testing across time periods or universes. Execution assumptions
are captured with each study so results remain reproducible.

See the [vector backtesting guide](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/vector-backtesting),
the [event backtesting guide](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/event-backtesting),
and the [tutorial notebooks](examples/tutorial/README.md).

</details>

<a id="backtest-storage"></a>
<details>
<summary><strong>Backtest Storage</strong></summary>
<br>

Each algorithm is stored as a versioned `.obtf` bundle using the
[Open Backtest Format](https://github.com/Quant-Commons/Open-Backtest-Format).
A bundle can contain studies, universes, windows, vector and event runs,
summaries, metrics, trades, orders, positions, snapshots, execution assumptions,
and Monte Carlo results.

The storage layer scales from local research to large result collections:

| Tier | Purpose |
| --- | --- |
| SQLite index | Rank and filter scalar metrics across 10,000+ results without decoding bundles |
| `BacktestStore` | Swap flat `LocalDirStore` and partitioned `LocalTieredStore` layouts |
| OHLCV chunks | Deduplicate content-addressed market data shared by multiple bundles |

```bash
iaf index ./my-backtests/
iaf rank ./my-backtests/ --by sharpe_ratio \
  --where "summary_number_of_trades > 50" -n 20
iaf list ./my-backtests/ --sort calmar_ratio --json
iaf migrate-store --from local-dir --src ./my-backtests/ \
  --to local-tiered --dst ./tiered/
```

See the [storage layer example](examples/storage_layer_demo/README.md).

</details>

<a id="deployment"></a>
<details>
<summary><strong>Deployment</strong></summary>
<br>

The same strategy can run locally, in a container, as a web service, or in a
serverless function. Portfolio state, orders, trades, and positions can persist
across runs.

### Live Trading

Connect to supported exchanges through CCXT or implement an `OrderExecutor` for
a broker, FIX gateway, or custom venue. Live mode evaluates schedules, loads
market data, creates orders, and maintains portfolio state continuously.

### Paper Trading

Paper trading exercises the live strategy path without sending real orders.
Use it after event-driven validation to verify schedules, data feeds, credentials,
and operational behavior in current market conditions.

### Self-Hosted and Serverless

Run the application on your own machine or infrastructure, package it in Docker,
or scaffold AWS Lambda and Azure Functions projects from the CLI:

```bash
pip install investing-algorithm-framework
investing-algorithm-framework init
investing-algorithm-framework init --type aws_lambda
investing-algorithm-framework init --type azure_function
```

### Finterion

Publish validated strategies to the
[Finterion marketplace](https://www.finterion.com/) so investors can subscribe
to them. The Finterion plugin handles the framework integration.

<p align="center">
  <a href="https://www.finterion.com/" target="_blank">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="static/features/marketplace-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="static/features/marketplace-light.svg">
      <img src="static/features/marketplace-dark.svg" alt="Finterion marketplace integration" style="max-width: 100%;">
    </picture>
  </a>
</p>

See the [deployment guide](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/deployment)
and [Finterion plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin).

</details>

<a id="portfolio-and-credentials-management"></a>
<details>
<summary><strong>Portfolio and Credentials Management</strong></summary>
<br>

`app.add_market()` configures a portfolio and its market credentials together.
Set the trading currency, starting balance, fees, slippage, position mode, and
paper-trading behavior in one place:

```python
app.add_market(
  market="BITVAVO",
  trading_symbol="EUR",
  initial_balance=10_000,
  fee_percentage=0.1,
  paper_trading=True,
)
```

Keep secrets outside source code with market-scoped environment variables:

```bash
BITVAVO_API_KEY=<your-api-key>
BITVAVO_SECRET_KEY=<your-api-secret>
```

Explicit credentials from a secret manager can be registered with
`MarketCredential`. Deployment-level `BITVAVO_OVERRIDE_*` variables can enforce
credentials, paper mode, and managed balance regardless of values supplied by
the application.

Portfolio state, orders, positions, and trades persist across runs. Optional
portfolio synchronization reconciles broker balances and supports recurring or
one-off deposit schedules. Local paper trading requires no real credentials.

See [Portfolio Configuration](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/portfolio-configuration),
[Credential Management](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/credentials),
and [Portfolio Synchronization](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/portfolio-sync).

</details>

<a id="dashboard"></a>
<details>
<summary><strong>Dashboard</strong></summary>
<br>

`BacktestReport` creates a self-contained interactive HTML dashboard. Compare
strategies, inspect equity and drawdown curves, review trades, analyze monthly
and yearly returns, check window coverage, and add research notes without
running a separate server.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="static/features/dashboard-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="static/features/dashboard-light.svg">
    <img src="static/features/dashboard-dark.svg" alt="Backtest analysis dashboard" style="max-width: 100%;">
  </picture>
</p>

```python
from investing_algorithm_framework import BacktestReport

# Materialize only the selected results when working with a large index.
BacktestReport(
    backtests=results.load_backtests(workers=1),
).save("backtest-report.html")

# Or reopen a directory of persisted bundles later.
BacktestReport.open(
    directory_path="./my-backtests/",
    workers=-1,
    show_progress=True,
).save("backtest-report.html")
```

The built-in MCP server lets compatible AI tools query stored backtests, compare
strategies, inspect trades, and work with report notes through
`investing-algorithm-framework mcp`.

See the [report guide](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/backtest-reports)
and [MCP server guide](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/mcp-server).

</details>

<a id="advanced-features"></a>
<details>
<summary><strong>Advanced Features</strong></summary>
<br>

- **Backtest optimization:** plug in an ask/tell `StrategyOptimizer`, budget candidate evaluations, and resume saved search state.
- **Long and short trading:** use open/close signals for either side with fill-based P&L and collateral handling.
- **Cross-sectional pipelines:** rank, filter, and score a universe of symbols on each iteration.
- **Confluence cards:** combine primary conditions, weighted evidence, requirements, vetoes, and score thresholds.
- **Decision traces:** retain indicator values, rule outcomes, and scores for signals and no-op decisions.
- **Risk rules:** configure position sizing, exposure limits, scaling, stop losses, take profits, and signal cooldowns.
- **Execution models:** use percentage, fixed, basis-point, or volume-aware commission and slippage models.
- **Monte Carlo testing:** estimate whether performance could plausibly occur by chance.
- **Metrics and benchmarks:** analyze CAGR, Sharpe, Sortino, Calmar, VaR/CVaR, drawdown, recovery, and benchmark-relative performance.
- **External data and custom variables:** load cached CSV, JSON, or Parquet data and record strategy-specific values.
- **Portfolio synchronization:** model recurring or one-off deposits and reconcile live balances with a broker.
- **Bounded execution:** control workers, memory admission, checkpoints, progress, and failure handling for large sweeps.

See the [advanced concepts documentation](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/)
and [backtest optimization guide](docusaurus/docs/Advanced%20Concepts/backtest-optimization.md).

</details>

<a id="position-modes"></a>
<details>
<summary><strong>Position Modes: NETTING vs. HEDGE</strong></summary>
<br>

Portfolios use `PositionMode.NETTING` by default: each symbol has one net
direction, so a long and short cannot coexist. Enable `PositionMode.HEDGE` to
maintain independent long and short legs for the same symbol, each with its own
entry, scaling, stop-loss, take-profit, cooldown, and P&L.

```python
from investing_algorithm_framework import PositionMode

app.add_market(
  market="BITVAVO",
  trading_symbol="EUR",
  initial_balance=10_000,
  position_mode=PositionMode.HEDGE,
)
```

Both backtest engines support `OPEN_LONG`, `CLOSE_LONG`, `OPEN_SHORT`, and
`CLOSE_SHORT` independently in HEDGE mode. In NETTING mode,
`flip_on_opposite_signal=True` can close the current direction and open the
opposite direction on the same bar.

Live HEDGE trading requires an `OrderExecutor` and `PortfolioProvider` that
explicitly support it. The built-in CCXT adapters support NETTING only, so use
custom HEDGE-capable adapters for live execution.

See [Position Modes: NETTING vs. HEDGE](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/position-modes).

</details>

<a id="pipelines"></a>
<details>
<summary><strong>Pipelines</strong></summary>
<br>

Pipelines compute factors across many symbols in one pass and return a tidy
cross-sectional table on each strategy iteration. Use them to define a tradeable
universe, rank candidates, normalize factors, and construct multi-factor or
risk-neutral signals without manually looping over symbols.

```python
from investing_algorithm_framework import AverageDollarVolume, Pipeline, Returns


class MomentumScreener(Pipeline):
  dollar_volume = AverageDollarVolume(window=30)
  momentum = Returns(window=30)

  universe = dollar_volume.top(100)
  alpha = momentum.rank(mask=universe)


class MomentumStrategy(TradingStrategy):
  pipelines = [MomentumScreener]

  def generate_signals(self, context, data):
    candidates = data["MomentumScreener"]
    leaders = candidates.sort("alpha", descending=True).head(10)
    # Yield Signal objects for the selected symbols.
    ...
```

Built-in factors include returns, liquidity, moving averages, RSI, volatility,
cross-sectional means, rolling beta, and neutralization. Factors compose with
arithmetic, ranking, filtering, z-scoring, demeaning, winsorization, and grouped
transforms.

See the [Pipelines guide](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines),
[event backtest integration](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines-event-backtest),
[vector backtest integration](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines-vector-backtest),
and [live integration](https://coding-kitties.github.io/investing-algorithm-framework/Advanced%20Concepts/pipelines-live).

</details>

<a id="monte-carlo-testing"></a>
<details>
<summary><strong>Monte Carlo Testing</strong></summary>
<br>

Monte Carlo permutation testing helps distinguish a strategy's observed edge
from results that randomized market paths could produce by chance. The framework
runs the strategy on its original OHLCV data, creates randomized permutations,
reruns the same strategy on each permutation, and compares the real metrics with
the resulting null distributions.

Use `app.run_monte_carlo_test(...)` with a strategy, a `BacktestDateRange`, and
the desired number of permutations. The returned `BacktestMonteCarloTest`
contains the real metrics, metrics from every permuted run, the original and
permuted datasets, and p-values for metrics including:

- CAGR, Sharpe, Sortino, and Calmar ratios
- Profit factor, win rate, and win/loss ratio
- Annual volatility and maximum drawdown
- Average monthly return

Lower p-values indicate that fewer randomized runs matched or exceeded the
observed result. They are evidence about statistical significance, not proof of
future profitability. Use enough permutations for the precision you need and
combine the result with out-of-sample and walk-forward validation.

See the [tutorial notebooks](examples/tutorial/README.md) for the robustness
analysis workflow.

</details>

<a id="plugins-and-supported-libraries"></a>
<details>
<summary><strong>Plugins and Supported Libraries</strong></summary>
<br>

| Integration | Purpose |
| --- | --- |
| [PyIndicators](https://github.com/coding-kitties/PyIndicators) | Technical indicators including EMA, RSI, and MACD |
| [Finterion plugin](https://github.com/Finterion/finterion-investing-algorithm-framework-plugin) | Publish and operate strategies on Finterion |
| [CCXT](https://github.com/ccxt/ccxt) | Exchange market data and live order execution |
| Pandas and Polars | Native tabular inputs for strategy and backtest workflows |
| Yahoo Finance, Alpha Vantage, and Polygon | Built-in market data providers |
| AWS and Azure | Optional state storage and serverless deployment integrations |

Custom data providers, order executors, storage adapters, strategies, metrics,
and optimizers can be added without replacing the core workflow.

</details>

## Development & Contributing

Contributions are welcome. Open an issue, choose an existing one, or submit a
pull request against the `dev` branch.

```bash
git clone https://github.com/coding-kitties/investing-algorithm-framework.git
cd investing-algorithm-framework
poetry install
python -m unittest discover -s tests
```

- [Open an issue](https://github.com/coding-kitties/investing-algorithm-framework/issues/new)
- [Contributing guide](https://coding-kitties.github.io/investing-algorithm-framework/Contributing%20Guide/contributing)
- [Architecture references](docs/architecture/README.md)

## Resources

- [Documentation](https://coding-kitties.github.io/investing-algorithm-framework/)
- [Quick start](https://coding-kitties.github.io/investing-algorithm-framework/Getting%20Started/installation)
- [Tutorial notebooks](examples/tutorial/README.md)
- [Strategy showcase](examples/algorithm_examples/strategies_showcase/README.md)
- [Discord](https://discord.gg/dQsRmGZP)
- [Reddit](https://www.reddit.com/r/InvestingBots/)

## Risk Disclaimer

Do not risk money you cannot afford to lose. Backtests and paper trading cannot
guarantee future performance. Validate strategy behavior, execution assumptions,
stored results, and operational safeguards before trading with real funds. The
project and its contributors assume no responsibility for investment results.

## Acknowledgements

Thank you to everyone who has contributed code, documentation, testing, ideas,
and feedback. See [AUTHORS.md](AUTHORS.md) for the contributor list.

## Sponsors

<p align="center">
  <a href="https://www.finterion.com/" target="_blank">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="static/sponsors/finterion-dark.png">
      <source media="(prefers-color-scheme: light)" srcset="static/sponsors/finterion-light.png">
      <img src="static/sponsors/finterion-light.png" alt="Finterion" width="180">
    </picture>
  </a>
</p>

[Finterion](https://www.finterion.com/) is a marketplace for trading bots where
strategy creators can publish and monetize their work.
