---
sidebar_position: 2
---

# Application Setup

A real trading project usually has three concerns that pull in different
directions:

1. **Research**: exploring data, designing strategies and tuning parameters
   in Jupyter notebooks.
2. **Backtesting**: running reproducible historical simulations from a
   script.
3. **Production**: running the strategy live, deployed somewhere stable, with
   secrets, logging and a single entry point.

The Investing Algorithm Framework is designed to support all three from the
**same** strategy code. To make that work, we recommend the following
project layout for any non-trivial bot.

## Recommended Project Structure

```text
my_trading_bot/
├── app.py                  # Production entry point (live trading)
├── strategies/             # Strategy implementations (importable package)
│   ├── __init__.py
│   └── my_strategy.py
├── data_providers.py       # Custom data providers for your dataSource definitions in your strategies (OPTIONAL)
├── notebooks/              # Research notebooks and backtest analyses
│   ├── 01_data_exploration.ipynb
│   ├── 02_backtest_baseline.ipynb
│   ├── 03_in_sample_param_grid_search.ipynb
│   ├── 04_out_of_sample_param_grid_search.ipynb
│   ├── 05_overfitting_analysis.ipynb
│   └── 06_event_backtests.ipynb
├── data/                   # Downloaded market data (OHLCV, etc.)
├── backtest_results/       # Saved backtest bundles (.iafbt)
├── reports/                # Generated reports (HTML, CSV, etc.)
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

This creates the above files and folders, with `app.py` and a sample strategy
that you can modify. The `notebooks/` folder is left empty for you to fill with your research work.

### Why this layout?

- **`strategies/` is a package, not a script.** Both `app.py` (production)
  and `notebooks` import the same strategy class, so
  what you backtest is *exactly* what you deploy.
- **`notebooks/` is for exploration and backtesting only.** Notebooks should `import`
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

A strategy is **declarative**: you describe *what data you need* and *when
to buy or sell*, and the framework takes care of order routing, position
sizing, stop-losses and take-profits. The two functions you implement are
`generate_buy_signals` and `generate_sell_signals` — both return a
boolean `pd.Series` per symbol.

```python
from typing import Any, Dict

import pandas as pd
from pyindicators import sma, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy,
    DataSource,
    DataType,
    TimeUnit,
)


class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]

    data_sources = [
        DataSource(
            identifier="btc_ohlcv_1h",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="1h",
            market="BITVAVO",
            window_size=200,
            pandas=True,
        ),
    ]

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        df = data["btc_ohlcv_1h"]
        df = sma(df, period=20, source_column="Close", result_column="sma_fast")
        df = sma(df, period=50, source_column="Close", result_column="sma_slow")
        df = crossover(df, "sma_fast", "sma_slow", result_column="cross_up")

        return {"BTC": df["cross_up"].fillna(False).astype(bool)}

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        df = data["btc_ohlcv_1h"]
        df = sma(df, period=20, source_column="Close", result_column="sma_fast")
        df = sma(df, period=50, source_column="Close", result_column="sma_slow")
        df = crossunder(df, "sma_fast", "sma_slow", result_column="cross_down")

        return {"BTC": df["cross_down"].fillna(False).astype(bool)}
```

> The framework instantiates the class for you, so pass the **class**
> (not an instance) to `app.add_strategy(...)`.

The same `generate_buy_signals` / `generate_sell_signals` functions are
used by **both** the vector backtest engine and the event-driven engine,
which is what guarantees that what you backtest is what you deploy. For
custom entry/exit logic that doesn't fit signals (e.g. rebalancing across
symbols), override `run_strategy` instead see [Strategies](./strategies)
for advanced patterns including position sizing, stop-loss, take-profit
and scale-in rules.

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
    market="bitvavo",
    trading_symbol="EUR",
    initial_balance=1000,
)
app.add_strategy(MyStrategy)


if __name__ == "__main__":
    app.run()
```

API keys belong in environment variables (`.env`), not in source. Use
`.env.example` to document which variables are required.

## The Backtest Entry Point (`run_backtest.py`)

`run_backtest.py` mirrors `app.py` but calls `run_backtest(...)` instead
of `run()`. Because both files import the same `MyStrategy`, the strategy
under test is identical to the one that will run live.

```python
from datetime import datetime, timezone

from investing_algorithm_framework import create_app, BacktestDateRange

from strategies.my_strategy import MyStrategy

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR")
app.add_strategy(MyStrategy)


if __name__ == "__main__":
    backtest_date_range = BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    backtest = app.run_backtest(
        backtest_date_range=backtest_date_range,
        initial_amount=1000,
    )

    summary = backtest.backtest_summary
    print(f"Total return: {summary.total_growth_percentage:.2f}%")
    print(f"Sharpe ratio: {summary.sharpe_ratio:.2f}")
```

## The Notebooks (`notebooks/`)

Notebooks are for research, backtesting, data exploration, signal visualisation,
parameter sweeps, robustness checks, final reporting. They should
**import** strategies from your `strategies/` package rather than
redefining them.

A typical progression (mirroring `examples/tutorial/notebooks/`):

| Notebook | Purpose |
| --- | --- |
| `01_data_exploration.ipynb` | Download OHLCV, inspect coverage, detect and fill gaps |
| `02_backtest_baseline.ipynb` | Single vector backtest of the strategy with default parameters + HTML report |
| `03_in_sample_param_grid_search.ipynb` | Grid search across thousands of parameter combinations on the in-sample window |
| `04_out_of_sample_param_grid_search.ipynb` | Re-run top in-sample candidates on the held-out out-of-sample window |
| `05_overfitting_analysis.ipynb` | Compare in-sample vs out-of-sample performance, walk-forward / permutation checks |
| `06_event_backtests.ipynb` | Validate the final picks with the event-driven engine (fees, slippage, fills) |

See the [tutorial README](https://github.com/coding-kitties/investing-algorithm-framework/tree/main/examples/tutorial)
for fully worked-out versions.

## Running the Application

### Live trading

```bash
python app.py
```

### Research and backtesting

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
