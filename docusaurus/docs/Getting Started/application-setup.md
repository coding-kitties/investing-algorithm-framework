---
sidebar_position: 2
---

# Application Setup

The framework is designed to support research, backtesting and production from the same strategy code. To make that work, we recommend a project layout that separates concerns and keeps research and production in sync.

A typical workflow looks like this:

1. **Research** — exploring data, designing strategies and tuning parameters
   in Jupyter notebooks.
2. **Backtesting** — running reproducible historical simulations from a
   script.
3. **Production** — running the strategy live, deployed somewhere stable, with
   secrets, logging and a single entry point.

The Investing Algorithm Framework is designed to support all three from the
**same** strategy code. To make that work, we recommend the following
project layout for any non-trivial bot.

Our cli also supports this layout for production deployments for both Azure and AWS Lambda. See [How to deploy a trading bot](/deployment) for details.

## Recommended Project Structure

```text
<project_name>/
├── app.py                  # Production entry point (live trading)
├── run_backtest.py         # Backtest entry point
├── strategies/             # Strategy implementations (importable package)
│   ├── __init__.py
│   └── my_strategy.py
├── data_providers.py       # DataSource definitions shared by strategies
├── notebooks/              # Research notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_strategy_visualization.ipynb
│   ├── 03_backtest_baseline.ipynb
│   └── 04_param_grid_search.ipynb
├── data/                   # Downloaded market data (OHLCV, etc.)
├── backtest_results/       # Saved backtest bundles (.obft)
├── resources/              # Misc assets (databases, configs)
├── requirements.txt
├── .env.example
└── README.md
```

A working example of this layout lives in
[`examples/tutorial`](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/tutorial).

You can scaffold this structure with the framework's CLI:

```bash
investing-algorithm-framework init --path ./my_trading_bot
```

This generates `app.py`, `run_backtest.py`, `strategies/`, `data_providers.py`,
`requirements.txt` and `.env.example` for you.

### Why this layout?

- **`strategies/` is a package, not a script.** Both `app.py` (production)
  and `run_backtest.py` (research) import the same strategy class, so
  what you backtest is *exactly* what you deploy.
- **`notebooks/` is for exploration only.** Notebooks should `import`
  from `strategies/` and `data_providers.py` — never copy-paste strategy
  code into a cell. This keeps research and production in sync.
- **`data/` and `backtest_results/` are caches.** They should usually
  be in `.gitignore`. The framework writes data downloads to `data/`
  and backtest bundles to `backtest_results/`.
- **`app.py` does only what production needs** — load config, register
  the market and strategy, call `app.run()`. Nothing else.

## The Strategy (`strategies/my_strategy.py`)

This is the only file that contains your trading logic. It is imported
by `app.py`, `run_backtest.py` and your notebooks alike.

```python
from typing import Any, Dict

from investing_algorithm_framework import (
    TradingStrategy,
    TimeUnit,
    Context,
)


class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
      """
      Vector backtest entry point. Called once per backtest, with all data loaded.
      """
        ...

    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
      """
      Event backtest and live trading entry point. Called once per time step, with only the current data.
      """
        ...
```

## The Production Entry Point (`app.py`)

> The framework instantiates the class for you, so pass the **class**
> (not an instance) to `app.add_strategy(...)`. You can also pass an instance.

`app.py` is the file you run in production (locally, in a container, or as
a serverless function). It should be small, declarative, and free of any
research code.

```python
import logging.config

from dotenv import load_dotenv

from investing_algorithm_framework import create_app, DEFAULT_LOGGING_CONFIG

from strategies.my_strategy import MyStrategy

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

app = create_app()
app.add_market(
    market="bitvavo",
    trading_symbol="EUR",
    initial_balance=1000,
)
app.add_strategy(MyStrategy) # Or app.add_strategy(MyStrategy()) if you prefer to pass an instance


if __name__ == "__main__":
    app.run()
```

> Market credentials are automatically loaded from the `.env` file using the expected naming convention. See [Credential Management](credentials) for all the ways to configure API keys and secrets.

## The Backtest Entry Point (`run_backtest.py`)

`run_backtest.py` mirrors `app.py` but calls `run_backtest(...)` instead
of `run()`. Because both files import the same `MyStrategy`, the strategy
under test is identical to the one that will run live.

Backtests are configured through a `Study`: it bundles the `Universe`
(market, trading symbol), the initial capital and one or more
`BacktestWindow`s to run over. Setting `engines=[BacktestEngine.VECTOR]`
runs the fast, vectorized engine — use this when `MyStrategy` implements
`generate_signal_series`. Omit `engines` to let the framework auto-detect
the engine from the strategy instead.

```python
from datetime import datetime, timezone

from investing_algorithm_framework import (
    create_app,
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    Study,
    Universe,
    StudySampleType
)

from strategies.my_strategy import MyStrategy

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR")
app.add_strategy(MyStrategy)


if __name__ == "__main__":
    study = Study(
        name="my_strategy",
        universe=Universe(market="bitvavo", trading_symbol="EUR"),
        initial_capital=1000,
        engines=[BacktestEngine.VECTOR],
        sample_type=StudySampleType.EXPLORATORY,
        backtest_windows=[
            BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
                    end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ),
                name="test_window",
            )
        ],
    )

    backtests = app.run_backtest(study=study, strategy=MyStrategy)
    backtest = backtests[0]

    summary = backtest.get_summary("vector")
    print(f"Total return: {summary.total_growth_percentage:.2f}%")
    print(f"Sharpe ratio: {summary.sharpe_ratio:.2f}")
```

## The Notebooks (`notebooks/`)

Notebooks are for research — data exploration, signal visualisation,
parameter sweeps, robustness checks, final reporting. They should
**import** strategies from your `strategies/` package rather than
redefining them.

A typical progression (mirroring `examples/tutorial/notebooks/`):

| Notebook | Purpose |
| --- | --- |
| `01_data_exploration.ipynb` | Download OHLCV, detect/fill gaps |
| `02_strategy_visualization.ipynb` | Plot indicators and signals |
| `03_backtest_baseline.ipynb` | Single vector backtest + report |
| `04_param_grid_search.ipynb` | Grid search across thousands of combos |
| `05_backtest_optimized.ipynb` | Best params re-run with checkpoints |
| `06_event_backtest.ipynb` | Validate top picks with the event-driven engine |
| `07_robustness_analysis.ipynb` | Walk-forward / permutation tests |
| `08_final_analysis.ipynb` | Rank, filter, compare, export |

See the [tutorial README](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/tutorial)
for fully worked-out versions.

## Running the Application

### Live trading

```bash
python app.py
```

### Backtesting

```bash
python run_backtest.py
```

### Research

```bash
jupyter lab notebooks/
```

## Next Steps

- [Strategies](./strategies) — designing the `run_strategy` body, declaring
  data sources, position sizing, stop-losses and take-profits.
- [Portfolio Configuration](./portfolio-configuration) — fees, slippage,
  multi-market portfolios.
- [Event Backtesting](./event-backtesting) and
  [Vector Backtesting](./vector-backtesting) — the two backtest engines
  and when to use which.
- [Deployment](./deployment) — packaging `app.py` for AWS Lambda, Azure
  Functions or a long-running container.
