# Investing Algorithm Framework Tutorial

This tutorial demonstrates main capabilities of the **Investing Algorithm Framework**
through a series of Jupyter notebooks. Each notebook focuses on a specific aspect of
the framework, from data handling to advanced backtesting and analysis.

> **Note**: This tutorial only showcases a subset of the framework's capabilities. Advanced features like cross-sectional pipelines can be explored in the [advanced tutorials](../advanced_tutorials/cross-sectional-pipelines/README.md).
>
> **Note**: This tutorial uses the Bitvavo exchange with EUR as the trading symbol.
> You can adapt the examples to other exchanges and symbols supported by the framework.

## 📋 Table of Contents

- [Overview](#overview)
- [Tutorial Structure](#tutorial-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Notebooks](#notebooks)
- [Key Framework Features](#key-framework-features)
- [Next Steps](#next-steps)

## 🎯 Overview

The Investing Algorithm Framework is a comprehensive Python library for building,
testing, and deploying algorithmic trading strategies. This tutorial showcases:

- **Data Management** - Download, validate, and fill missing market data
- **Strategy Visualization** - Visualize trading strategies
- **In sample Parameter Sweeping** - Test thousands of parameter combinations with ease through a grid search and vector backtesting.
- **In sample Event Validation** - Quick, cheap sanity check of the top 10 in-sample winners with the event-driven engine on just the first rolling window.
- **Out sample Vector Backtesting** - Test thousand of strategies out-of-sample with a fast vectorized backtester.
- **Out sample event based Backtesting** - Simulate realistic trade execution with an event-based backtester to validate top strategies from the vector backtest.
- **Final analysis** - Generate reports, rank strategies, and export results for further analysis.

## 📁 Tutorial Structure

```
tutorial/
├── README.md                          # This file
├── notebooks/                         # Tutorial notebooks (start here!)
│   ├── 01_data_exploration.ipynb      # Data download and validation
│   ├── 02_strategy_visualization.ipynb # Strategy logic visualization
│   ├── 03_in_sample_param_sweep.ipynb           # In-sample parameter optimization
│   ├── 04_in_sample_event_validation.ipynb      # Quick in-sample event sanity check (top 10, first window)
│   ├── 05_out_sample_vector_backtest.ipynb    # Out-of-sample vector backtesting
│   ├── 06_event_backtest.ipynb        # Out-of-sample event-based backtesting
│   ├── 07_robustness_analysis.ipynb   # Robustness and validation
│   └── 08_final_analysis.ipynb        # Final results and reporting
├── strategies/                        # Strategy implementations
│   └── supertrend_ema_confirmation/   # Example strategy (v9 signal API)
├── data/                              # Downloaded market data
├── backtest_results/                  # Backtest results storage
└── reports/                           # Generated reports / figures
```

## 🔧 Prerequisites

### Required Knowledge
- Basic Python programming
- Understanding of financial markets and trading concepts
- Familiarity with technical indicators (EMA, RSI, MACD, etc.)
- Basic knowledge of Jupyter notebooks

### Software Requirements
- Python 3.10 or higher
- Jupyter Notebook or JupyterLab

### Installation

```bash
# Install the framework
pip install investing-algorithm-framework

# Install additional dependencies
pip install plotly pyindicators
```

## 🚀 Getting Started

1. **Navigate to the tutorial directory**:
   ```bash
   cd examples/tutorial
   ```

2. **Start Jupyter**:
   ```bash
   jupyter notebook
   ```

3. **Open the notebooks folder** and start with `01_data_exploration.ipynb`

4. **Follow the notebooks in order** - each builds on the previous one

## 📓 Notebooks

### 01 - Data Exploration
**File**: `notebooks/01_data_exploration.ipynb`

Learn how to download and manage market data:
- **`download_v2()`** - Download OHLCV data with path tracking
- **`get_missing_timeseries_data_entries()`** - Detect gaps in data
- **`fill_missing_timeseries_data()`** - Fill missing data points
- **`DownloadResult`** - Access both data and file path

```python
from investing_algorithm_framework import download_v2

result = download_v2(
    symbol="BTC/EUR",
    market="BITVAVO",
    time_frame="2h",
    start_date=start_date,
    end_date=end_date,
    save=True,
    storage_path="./data"
)
print(result.data)  # DataFrame
print(result.path)  # File path where data was saved
```

---

### 02 - Strategy Visualization
**File**: `notebooks/02_strategy_visualization.ipynb`

Visualize and understand strategy logic:
- Plot indicators (EMA, RSI) on price charts
- Visualize buy/sell signals
- Understand strategy parameters
- Interactive Plotly charts

---

### 03 - In-Sample Parameter Sweep
**File**: `notebooks/03_in_sample_param_sweep.ipynb`

Define a grid of strategy variants and screen all of them with the fast vectorized engine over rolling walk-forward windows:

- **`Study`** - Bundles the universe, rolling `backtest_windows`, and engine choice (`engines=[BacktestEngine.VECTOR]`)
- **`generate_rolling_backtest_windows()`** - Train/test rolling windows with a gap between them
- **`app.run_backtest(strategies=..., study=...)`** - Batch vector backtest across the whole grid, with `window_filter_function` progressively pruning weak variants
- **`build_index()` / `rank_index()`** - Rank thousands of on-disk bundles in milliseconds via the Tier-1 SQLite index
- **`promote_backtests()`** - Copy just the top-N winners into a dedicated `top_selection/` folder for the next notebooks

```python
from datetime import datetime, timezone
from investing_algorithm_framework import (
    generate_rolling_backtest_windows, Study, Universe, BacktestEngine,
    WindowPart, StudySampleType,
)

rolling_windows = generate_rolling_backtest_windows(
    start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2025, 12, 30, tzinfo=timezone.utc),
    train_days=365, test_days=180, gap_days=30, step_days=90,
)

in_sample_study = Study(
    name="in_sample_param_sweep",
    sample_type=StudySampleType.IN_SAMPLE,
    universe=Universe(symbols=["BTC", "ETH", "ADA", "SOL", "DOT"], trading_symbol="EUR", market="BITVAVO"),
    backtest_windows=rolling_windows,
    window_part=WindowPart.TEST,
    engines=[BacktestEngine.VECTOR],
)

backtests = app.run_backtest(
    strategies=strategies,
    study=in_sample_study,
    backtest_storage_directory=backtest_results_dir,
    show_progress=True,
)
```

---

### 04 - In-Sample Event Validation (Quick Sanity Check)
**File**: `notebooks/04_in_sample_event_validation.ipynb`

Before spending the (slower) out-of-sample vector budget on the whole `top_selection/` folder, replay just the **top 10** in-sample winners with the **event-driven** engine on **only the first rolling window** — a cheap sanity check that the vector engine's numbers roughly hold up once orders are routed bar-by-bar. This is also the showcase for the newest study-reuse convenience API:

- **`get_backtests(storage_dir, algorithm_ids)`** / **`get_backtest(storage_dir, algorithm_id)`** - Reload specific saved bundles by id, no need to rank/open the whole directory again
- **`Backtest.get_study_definition(name)`** - Pull a study straight off a loaded bundle (universe, windows, execution assumptions carried over, `engine_results` reset) instead of re-declaring it by hand
- Slice `study.backtest_windows` down to the windows you actually want to (re-)run, and swap `study.engines`
- `app.run_backtest(..., backtest_storage_directory=<same dir>)` merges the new engine's results into the **same** `<algorithm_id>.obtf` bundle automatically

```python
from investing_algorithm_framework import BacktestEngine, get_backtest, get_backtests

top_10_backtests = get_backtests(str(top_selection_path), top_10_ids)

reference_backtest = get_backtest(str(top_selection_path), top_10_ids[0])
event_study = reference_backtest.get_study_definition("in_sample_param_sweep")

# Only the first window, only the event engine.
event_study.backtest_windows = event_study.backtest_windows[:1]
event_study.engines = [BacktestEngine.EVENT_DRIVEN]

backtests = app.run_backtest(
    strategies=top_10_strategies,
    study=event_study,
    backtest_storage_directory=str(top_selection_path),
)
```

---

### 05 - Out-of-Sample Vector Backtest
**File**: `notebooks/05_out_sample_vector_backtest.ipynb`

Re-instantiate the in-sample winners on two out-of-sample regimes — a different time window (Type A) and a disjoint symbol universe (Type B) — still with the fast vector engine:

- **`Study`** per regime, each with its own `sample_type` (`OUT_SAMPLE_TIME` / `OUT_SAMPLE_UNIVERSE`) and `Universe`
- Bundles saved to the same `top_selection/` folder as notebook 03, so each regime's results land as an extra study slot on the existing `<algorithm_id>.obtf` bundle

---

### 06 - Out-of-Sample Event Backtest
**File**: `notebooks/06_event_backtest.ipynb`

Full event-driven replay of both out-of-sample regimes (every rolling window, not just the first), scoped to whichever winners still look robust:

- **`rank_by_cross_study_robustness()`** - Scores how much of the in-sample edge each bundle retained out-of-sample, so the (slow) event engine only runs on the most credible survivors
- **`Backtest.get_study_definition(name)`** for both OOS studies, `engines=[BacktestEngine.EVENT_DRIVEN]`
- `show_backtest_summaries()` / `show_backtest_runs()` side by side for `engine="vector"` vs `engine="event"`

---

### 07 - Robustness Analysis
**File**: `notebooks/07_robustness_analysis.ipynb`

Cross-study robustness scoring and window-stability analysis across everything produced so far.

---

### 08 - Final Analysis
**File**: `notebooks/08_final_analysis.ipynb`

Generate final reports and analysis:
- **`create_markdown_table()`** - Format results as markdown
- **`BacktestReport`** - Interactive HTML reports
- Export results for further analysis
- Compare top strategies

```python
from investing_algorithm_framework import create_markdown_table

# Create summary table
table = create_markdown_table(
    backtests,
    sort_by="sharpe_ratio",
    top_n=10
)
print(table)
```

## 🔑 Key Framework Features

### Strategy API (v9)

Strategies declare **what** to do; the framework handles **how much**
and **how**. The example `SupertrendEmaConfirmationStrategy` implements
both signal methods so it works in either backtest mode:

| Method | Used by | Returns |
|--------|---------|---------|
| `generate_signals(context, data)` | event backtest / live | one or more `Signal(symbol, side, ...)` for the latest bar |
| `generate_signal_series(data)` | vector backtest | one `SignalSeries` per `(symbol, side)` covering the whole window |

Sizing lives on the class as a list of `PositionSize` rules
(`percentage_of_portfolio=...` or `fixed_amount=...`). Risk attachments
(`StopLossRule`, `TakeProfitRule`, `ScalingRule`, `CooldownRule`) attach
to orders automatically. See `docs/architecture/strategy.md` for the
full contract.

### Data Management
| Function | Description |
|----------|-------------|
| `download()` | Download market data |
| `download_v2()` | Download with path tracking |
| `fill_missing_timeseries_data()` | Fill gaps in time series |
| `get_missing_timeseries_data_entries()` | Detect missing data |

### Backtesting
| Function | Description |
|----------|-------------|
| `run_backtest()` | Single strategy backtest (vector or event engine, via `Study.engines`) |
| `run_backtests()` | Batch backtest across many strategies (vector or event engine, via `Study.engines`) |

### Analysis & Ranking
| Function | Description |
|----------|-------------|
| `rank_results()` | Rank backtests by metrics |
| `create_weights()` | Custom ranking weights |
| `BacktestEvaluationFocus` | Predefined ranking focuses |
| `create_markdown_table()` | Format results as markdown |

### Storage & Checkpointing
| Feature | Description |
|---------|-------------|
| `backtest_storage_directory` | Persist results to disk |
| `use_checkpoints` | Save/resume experiments |
| `load_backtests_from_directory()` | Load saved backtests |

### Parallel Processing
| Feature | Description |
|---------|-------------|
| `n_workers` | Number of parallel workers |
| `batch_size` | Strategies per batch |

## 🎓 Next Steps

After completing this tutorial:

1. **Create your own strategy** using the example as a template
2. **Test on different markets** and time periods
3. **Deploy to paper trading** to validate in real-time
4. **Go live** with the framework's production capabilities

### Additional Resources

- **Documentation**: See `docusaurus/docs/` for full documentation
- **Example Strategies**: See `examples/strategies_showcase/`
- **Advanced Topics**:
  - `docusaurus/docs/Advanced Concepts/vector-backtesting.md`
  - `docusaurus/docs/Advanced Concepts/PARALLEL_PROCESSING_GUIDE.md`

## 📧 Support

- Check the main framework documentation
- Review example strategies in `examples/`
- Open an issue on GitHub

---

**Happy Trading! 🚀📈**

*Remember: Past performance does not guarantee future results. Always test thoroughly and use proper risk management.*
