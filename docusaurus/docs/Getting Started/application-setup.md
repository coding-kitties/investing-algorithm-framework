---
sidebar_position: 2
---

# Application Setup

The framework is designed to support research, backtesting and production from the same strategy code. To make that work, we recommend a project layout that separates concerns and keeps research and production in sync.

For a complete runnable version of the code on this page, see
[`examples/simple_app.py`](https://github.com/coding-kitties/investing-algorithm-framework/blob/main/examples/simple_app.py).
It runs the same confluence-card strategy in vector, event-driven and paper
trading modes.

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
├── backtest_results/       # Saved backtest bundles (.obtf)
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
from pyindicators import crossover, crossunder, ema, rsi

from investing_algorithm_framework import (
  ConfluenceCard,
  DataSource,
  DataType,
  EvidenceGroup,
  Operator,
  PrimaryGroup,
  Schedule,
  ScoreRule,
  SignalSide,
    TradingStrategy,
    TimeUnit,
  condition,
)


def create_card(name, rsi_operator, rsi_value, cross_column):
  return ConfluenceCard(
    name=name,
    primary=PrimaryGroup(
      name="RSI reversal",
      rules=(ScoreRule(
        name="RSI condition",
        expression=condition(
          "rsi", rsi_operator, value=rsi_value
        ),
        points=3,
      ),),
      minimum_matches=1,
    ),
    secondary=(EvidenceGroup(
      name="EMA confirmation",
      rules=(ScoreRule(
        name="Recent EMA cross",
        expression=condition(
          cross_column, Operator.GT, value=0
        ),
        points=2,
      ),),
      minimum_score=2,
    ),),
    minimum_score=5,
  )


class MyStrategy(TradingStrategy):
  strategy_id = "rsi_ema_crossover"
  schedule = Schedule.every(2, TimeUnit.HOUR)
  symbols = ["BTC"]
  data_sources = [DataSource(
    identifier="BTC_ohlcv",
    symbol="BTC/EUR",
    data_type=DataType.OHLCV,
    time_frame="2h",
    market="BITVAVO",
    pandas=True,
    warmup_window=100,
  )]

  signal_cards = {
    SignalSide.OPEN_LONG: create_card(
      "Open long", Operator.LT, 30, "recent_crossover"
    ),
    SignalSide.CLOSE_LONG: create_card(
      "Close long", Operator.GTE, 70, "recent_crossunder"
    ),
    SignalSide.OPEN_SHORT: create_card(
      "Open short", Operator.GTE, 70, "recent_crossunder"
    ),
    SignalSide.CLOSE_SHORT: create_card(
      "Close short", Operator.LT, 30, "recent_crossover"
    ),
  }

  def prepare_signal_data(self, data):
    frame = data["BTC_ohlcv"].copy()
    frame = ema(frame, "Close", 12, "ema_short")
    frame = ema(frame, "Close", 26, "ema_long")
    frame = crossover(
      frame, "ema_short", "ema_long", "ema_crossover"
    )
    frame = crossunder(
      frame, "ema_short", "ema_long", "ema_crossunder"
    )
    frame = rsi(frame, "Close", 14, "rsi")
    frame["recent_crossover"] = (
      frame["ema_crossover"].rolling(10).max()
    )
    frame["recent_crossunder"] = (
      frame["ema_crossunder"].rolling(10).max()
    )
    return {"BTC": frame}
```

The base `TradingStrategy` evaluates these cards for both vector and event
execution, so the strategy does not need separate signal-generation methods.
The [complete simple app](https://github.com/coding-kitties/investing-algorithm-framework/blob/main/examples/simple_app.py)
also demonstrates position sizing, scaling, exposure, stop-loss, take-profit
and cooldown rules.

## The Production Entry Point (`app.py`)

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
  market="BITVAVO",
    trading_symbol="EUR",
  initial_balance=10_000,
  fee_percentage=0.1,
  paper_trading=True,
)
app.add_strategy(MyStrategy())


if __name__ == "__main__":
  app.run(run_immediately_on_start=True)
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
  BacktestDateRange,
  BacktestEngine,
  BacktestRunConfiguration,
  BacktestWindow,
  Study,
  StudySampleType,
  Universe,
  create_app,
  Algorithm
)

from strategies.my_strategy import MyStrategy

app = create_app()
app.add_market(
  market="BITVAVO",
  trading_symbol="EUR",
  initial_balance=10_000,
  fee_percentage=0.1,
)


if __name__ == "__main__":
    study = Study(
        name="my_strategy",
        universe=Universe(
          key="btc_eur",
          symbols=["BTC"],
          market="BITVAVO",
          trading_symbol="EUR",
        ),
        initial_capital=10_000,
        engines=[BacktestEngine.VECTOR],
        sample_type=StudySampleType.IN_SAMPLE,
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
    algorithm = Algorithm(
      strategy=MyStrategy(),
    )
    results = app.run_backtest(
      study=study,
      algorithm=algorithm,
      run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./backtest_results",
        use_checkpoints=True,
        show_progress=True,
      ),
    )

    print(results.df)
    print(f"Backtest bundles: {results.directory}")
```

  `run_backtest()` returns a disk-backed `BacktestIndex`. Use its dataframe for
  fast filtering, then call `iter_backtests()` or `load_backtests()` when you
  need the complete persisted backtest objects.

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
