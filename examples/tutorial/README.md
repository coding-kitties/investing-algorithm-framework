# Investing Algorithm Framework Tutorial

This tutorial demonstrates the full capabilities of the **Investing Algorithm Framework** 
through a series of Jupyter notebooks. Each notebook focuses on a specific aspect of 
the framework, from data handling to advanced backtesting and analysis.

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
- **Strategy Development** - Create and visualize trading strategies
- **Vectorized Backtesting** - High-performance backtesting (10-100x faster)
- **Event-Based Backtesting** - Realistic trade simulation
- **Parameter Optimization** - Grid search across thousands of variations
- **Performance Analysis** - Ranking, filtering, and robustness testing
- **Checkpointing & Storage** - Save and resume long-running experiments

## 📁 Tutorial Structure

```
tutorial/
├── README.md                          # This file
├── notebooks/                         # Tutorial notebooks (start here!)
│   ├── 01_data_exploration.ipynb      # Data download and validation
│   ├── 02_strategy_visualization.ipynb # Strategy logic visualization
│   ├── 03_backtest_baseline.ipynb     # Basic backtesting
│   ├── 04_param_grid_search.ipynb     # Parameter optimization
│   ├── 05_backtest_optimized.ipynb    # Optimized strategy testing
│   ├── 06_event_backtest.ipynb        # Event-based backtesting
│   ├── 07_robustness_analysis.ipynb   # Robustness and validation
│   └── 08_final_analysis.ipynb        # Final results and reporting
├── strategies/                        # Strategy implementations
│   └── ema_crossover_rsi_filter/      # Example strategy
├── data/                              # Downloaded market data
├── backtests/                         # Backtest results storage
└── resources/                         # Additional resources
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

### 03 - Backtest Baseline
**File**: `notebooks/03_backtest_baseline.ipynb`

Run your first backtest:
- **`run_vector_backtest()`** - Single strategy vectorized backtest
- **`BacktestReport`** - Generate HTML reports
- Performance metrics (Sharpe ratio, max drawdown, win rate)

```python
backtest = app.run_vector_backtest(
    backtest_date_range=date_range,
    strategy=strategy,
    initial_amount=1000,
    risk_free_rate=0.027
)

report = BacktestReport(backtest)
report.show(browser=True)
```

---

### 04 - Parameter Grid Search
**File**: `notebooks/04_param_grid_search.ipynb`

Test thousands of parameter combinations:
- **`run_vector_backtests()`** - Batch vectorized backtesting
- **`rank_results()`** - Rank strategies by performance
- **`create_weights()`** - Custom ranking weights
- **Window filtering** - Filter after each date range
- **Final filtering** - Filter combined results

```python
# Create parameter grid
params = {
    'ema_short_period': [20, 50, 75],
    'ema_long_period': [100, 150, 200],
    'rsi_period': [14, 21],
}

# Generate all combinations
strategies = [Strategy(**p) for p in generate_combinations(params)]

# Run vectorized backtests with filtering
backtests = app.run_vector_backtests(
    backtest_date_ranges=date_ranges,
    strategies=strategies,
    window_filter_function=window_filter,
    final_filter_function=final_filter,
    show_progress=True
)

# Rank results
ranked = rank_results(
    backtests,
    focus=BacktestEvaluationFocus.BALANCED
)
```

---

### 05 - Backtest Optimized
**File**: `notebooks/05_backtest_optimized.ipynb`

Advanced backtesting features:
- **Parallel processing** - Use multiple CPU cores
- **Checkpointing** - Save/resume long experiments
- **Storage directories** - Persist results to disk

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=date_ranges,
    n_workers=-1,  # Use all CPU cores
    use_checkpoints=True,
    backtest_storage_directory="./backtests/experiment_1",
    show_progress=True
)
```

---

### 06 - Event Backtest
**File**: `notebooks/06_event_backtest.ipynb`

Realistic trade simulation:
- **`run_backtest()`** - Event-based backtesting
- **`run_backtests()`** - Batch event-based backtesting
- Simulates real-time order execution
- More accurate slippage and fill modeling

```python
# Single event-based backtest
backtest = app.run_backtest(
    backtest_date_range=date_range,
    initial_amount=1000
)

# Batch event-based backtests
backtests = app.run_backtests(
    backtest_date_ranges=date_ranges,
    strategies=strategies,
    n_workers=4
)
```

---

### 07 - Robustness Analysis
**File**: `notebooks/07_robustness_analysis.ipynb`

Validate strategy robustness:
- **Walk-forward analysis** - Rolling window validation
- **`generate_rolling_backtest_windows()`** - Create train/test splits
- Out-of-sample testing
- Parameter stability analysis

```python
from investing_algorithm_framework import generate_rolling_backtest_windows

windows = generate_rolling_backtest_windows(
    start_date=start_date,
    end_date=end_date,
    window_size=365,
    step_size=90
)

for window in windows:
    train_range = window["train_range"]
    test_range = window["test_range"]
    # Train on train_range, validate on test_range
```

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
| `run_vector_backtest()` | Single vectorized backtest |
| `run_vector_backtests()` | Batch vectorized backtests |
| `run_backtest()` | Single event-based backtest |
| `run_backtests()` | Batch event-based backtests |

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
- **Example Strategies**: See `examples/example_strategies/`
- **Advanced Topics**: 
  - `docs/Advanced Concepts/vector-backtesting.md`
  - `docs/Advanced Concepts/PARALLEL_PROCESSING_GUIDE.md`

## 📧 Support

- Check the main framework documentation
- Review example strategies in `examples/`
- Open an issue on GitHub

---

**Happy Trading! 🚀📈**

*Remember: Past performance does not guarantee future results. Always test thoroughly and use proper risk management.*

