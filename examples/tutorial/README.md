# Trading Strategy Discovery Tutorial

This tutorial demonstrates how to use the **Investing Algorithm Framework** to 
discover profitable trading strategies through systematic exploration and validation. 
The tutorial follows a complete basic workflow from strategy definition to 
validation using grid search, vectorized backtesting, and permutation testing.

> This tutorial does not validate the strategies for live trading through event-based backtesting and
> signal comparison. It focuses on the strategy discovery process. Final validation should be done separately.

## 📋 Table of Contents

- [Overview](#overview)
- [Tutorial Structure](#tutorial-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Tutorial Workflow](#tutorial-workflow)
- [Key Concepts](#key-concepts)
- [Example Strategies](#example-strategies)
- [Advanced Topics](#advanced-topics)
- [Next Steps](#next-steps)

## 🎯 Overview

This tutorial guides you through the basis of a professional 
strategy discovery process that includes:

1. **Strategy visualization** - Define and visualize strategy logic
2  **Parameter Grid Search** - Test thousands of strategy variations efficiently
3  **Vectorized Backtesting** - High-performance backtesting for rapid iteration
4  **Performance Ranking** - Identify top performers using customizable metrics
5  **Permutation Testing** - Validate strategy robustness and avoid overfitting

The goal is to identify robust trading strategies that 
perform well across different market conditions and are suitable for live trading.

## 📁 Tutorial Structure

This tutorial was made with the init command of the Investing Algorithm Framework.
```commandline
investing-algorithm-framework init --path .
```

The directory structure is as follows:

```
tutorial/
├── README.md                          # This file
├── exploration.ipynb                  # Main tutorial notebook
├── strategies/                        # Strategy implementations
│   └── ema_crossover_rsi_filter/     # EMA crossover with RSI filter
│       ├── strategy.py               # Strategy implementation
│       └── strategy_visualization.ipynb
├── resources/                         # Data storage
│   └── market_data/                  # Cached OHLCV data
├── backtests/                        # Backtest results storage
└── data/                             # Market data files (if any)
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
- Investing Algorithm Framework installed
- Pyindicators, Pandas, NumPy, Plotly for data handling and visualization

### Installation

```bash
# Install the framework
pip install investing-algorithm-framework

# Install additional dependencies for visualization, data handling and metrics
pip install plotly pandas numpy, pyindicators
```

## 🚀 Getting Started

1. **Clone or download** this tutorial directory

2. **Set up your environment**:
   ```bash
   cd tutorial
   ```

## 🔄 Tutorial Workflow

### Step 1: Strategy visualization

1. **Open the strategy visualization notebook** located at:
   `strategies/ema_crossover_rsi_filter/strategy_visualization.ipynb`
2. **Run the cells** to understand the strategy logic and visualize its behavior on sample data.
   - By default, the framework uses the Bitvavo exchange, with trading symbol "EUR" and symbol BTC/EUR.
   - Data is stored locally in `data`
3. **Interpret the visualizations** After running the cells in notebook, you should have a understanding of:
   1. how the EMA and RSI indicators behave on historical price data,
   2. how different parameter settings affect indicator values,
   3. the overall strategy logic,


### Step 2: Exploration and Parameter Grid Search

1. **Open the exploration notebook**: `exploration.ipynb`
The first step is to define a parameter grid for your trading strategy. This allows you to test multiple variations systematically.

```python
params = {
    'ema_short_period': [20, 50, 75],
    'ema_long_period': [100, 150, 200],
    'rsi_period': [14],
    'rsi_overbought_threshold': [60, 70],
    'rsi_oversold_threshold': [30, 40],
    'ema_timeframe': ['1h', '4h', '1d'],
    'rsi_timeframe': ['1h', '4h', '1d'],
}
```

This creates a grid of parameter combinations to test. The framework will 
generate all possible combinations automatically.

### Step 2: Run Vectorized Backtests

Vectorized backtesting is **10-100x faster** than traditional event-based backtesting, making it ideal for grid search.

```python
# Create strategies for all parameter combinations
strategies = [
    EMACrossoverRSIFFilterStrategy(**variant, metadata={"params": variant})
    for variant in param_variants
]

# Run vectorized backtests for all strategies
backtests = app.run_vector_backtests(
    backtest_date_range=evaluation_date_range,
    initial_amount=1000,
    strategies=strategies,
    risk_free_rate=0.027,
    show_progress=True
)
```

### Step 3: Rank and Filter Results

Use built-in ranking functions to identify the best-performing strategies based on your chosen focus (profit, risk-adjusted returns, trade frequency, etc.).

```python
from investing_algorithm_framework import rank_results

ranked = rank_results(
    backtests,
    filter_fn={
        "number_of_trades": lambda x: x > 1,  # Minimum trades filter
        "win_rate": lambda x: x > 0.5,        # Minimum win rate
    },
    focus="risk_adjusted"  # Focus on Sharpe ratio
)

top_strategies = ranked[:5]  # Get top 5 strategies
```

### Step 4: Validate with Permutation Testing

Permutation testing helps you determine if your strategy's performance is due to genuine edge or just luck/overfitting.

```python
# Test the best strategy with permuted data
permutation_test = app.run_permutation_test(
    strategy=best_strategy,
    backtest_date_range=evaluation_date_range,
    number_of_permutations=100
)

# Check if strategy beats random chance
print(permutation_test.summary())
```

A good strategy should significantly outperform the permuted (random) datasets, indicating that the strategy captures genuine market patterns rather than fitting to noise.

### Step 5: Analyze Results

Examine the performance metrics and visualizations to understand:
- **Total returns** and net profit
- **Risk metrics** (Sharpe ratio, max drawdown, volatility)
- **Trade statistics** (win rate, profit factor, average trade duration)
- **Consistency** across different time periods

## 🔑 Key Concepts

### Vectorized Backtesting

Traditional backtesting processes data point-by-point, simulating real-time execution. Vectorized backtesting processes entire datasets at once using vectorized operations (NumPy/Pandas), resulting in:

- **Speed**: 10-100x faster execution
- **Efficiency**: Ideal for testing thousands of strategy variations
- **Use Case**: Parameter optimization, grid search, initial screening

**When to use:**
- Strategy exploration and parameter tuning
- Testing large numbers of variations (100+)
- Rapid prototyping and iteration

**Limitations:**
- Less realistic execution simulation
- May not capture complex order dynamics
- Should be followed by event-based backtesting for final validation

### Parameter Grid Search

Grid search systematically tests all combinations of specified parameters. This helps you:

1. **Discover** optimal parameter ranges
2. **Identify** robust parameter regions (parameters that work across ranges)
3. **Avoid** overfitting to specific parameter values

**Best Practices:**
- Start with wide ranges, then narrow down
- Test at least 100+ combinations for meaningful results
- Look for parameter stability (nearby values should perform similarly)
- Validate top performers with out-of-sample testing

### Performance Ranking

The framework provides multiple ranking focuses:

- **`balanced`**: Equal weight to profit, risk, and trade frequency
- **`profit`**: Emphasizes total returns and profit
- **`risk_adjusted`**: Focuses on Sharpe ratio and risk metrics
- **`frequency`**: Prioritizes strategies with more trading opportunities

You can also create custom ranking weights for your specific objectives.

### Permutation Testing

Permutation testing shuffles the price data while preserving its statistical properties (volatility, distribution). If your strategy still performs well on randomized data, it may be overfitted to noise rather than capturing real patterns.

**Interpreting Results:**
- Strategy should rank in **top 5%** of permutations
- **p-value < 0.05** indicates statistical significance
- Large difference between real and permuted returns suggests genuine edge

### Walk-Forward Analysis

After identifying promising strategies through grid search and permutation testing, use walk-forward analysis to test out-of-sample performance:

1. **Training Period**: Use grid search to find optimal parameters
2. **Testing Period**: Apply those parameters to new, unseen data
3. **Rolling Window**: Repeat across multiple time periods

This provides a more realistic assessment of how the strategy will perform in live trading.

## 💡 Example Strategies

### EMA Crossover with RSI Filter

A trend-following strategy that combines:
- **EMA Crossover**: Identifies trend direction (short EMA crosses long EMA)
- **RSI Filter**: Confirms entry timing (oversold for buys, overbought for sells)

**Strategy Logic:**
- **Buy Signal**: Short EMA crosses above long EMA + RSI < oversold threshold
- **Sell Signal**: Short EMA crosses below long EMA + RSI > overbought threshold

**Configurable Parameters:**
- EMA periods (short and long)
- RSI period and thresholds
- Timeframes for each indicator
- Lookback window for crossover detection

**Files:**
- `strategies/ema_crossover_rsi_filter/strategy.py`
- `strategies/ema_crossover_rsi_filter/strategy_visualization.ipynb`

### MACD Divergence with EMA Cross

A strategy that combines momentum and trend:
- **MACD Divergence**: Identifies potential reversals
- **EMA Confirmation**: Validates trend direction

**Files:**
- `strategies/macd_divergence_ema_cross/`

## 🔬 Advanced Topics

### Parallel Processing

For very large parameter grids (1000+ strategies), use parallel processing:

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_range=date_range,
    n_workers=-1,  # Use all CPU cores
    show_progress=True
)
```

### Checkpointing

Save intermediate results to avoid losing progress on long-running experiments:

```python
backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_range=date_range,
    use_checkpoints=True,
    backtest_storage_directory="./backtests/experiment_1"
)
```

If the process is interrupted, it will resume from the last checkpoint.

### Window Filtering

Apply filters after each date range in a walk-forward analysis:

```python
def window_filter(backtests, date_range):
    """Keep only strategies with positive returns in this window"""
    return [b for b in backtests if b.total_return > 0]

backtests = app.run_vector_backtests(
    strategies=strategies,
    backtest_date_ranges=[range1, range2, range3],
    window_filter_function=window_filter
)
```

### Custom Ranking Metrics

Create custom ranking weights for your specific goals:

```python
from investing_algorithm_framework import create_weights

custom_weights = create_weights(
    custom_weights={
        'sharpe_ratio': 0.3,
        'total_return': 0.3,
        'max_drawdown': 0.2,  # Lower is better (inverted automatically)
        'number_of_trades': 0.2
    }
)

ranked = rank_results(backtests, weights=custom_weights)
```

## 🎓 Next Steps

After completing this tutorial, you should:

1. **Modify the strategy parameters** to explore different ranges
2. **Try different evaluation periods** to test robustness across time
3. **Implement your own strategy** using the provided examples as templates
4. **Validate top strategies** with event-based backtesting:
   ```python
   # More realistic simulation for final validation
   backtest = app.run_backtest(
       strategy=best_strategy,
       backtest_date_range=validation_period
   )
   ```
5. **Paper trade** promising strategies before committing real capital
6. **Deploy to production** using the framework's live trading capabilities

### Additional Resources

- **Framework Documentation**: [Link to docs]
- **Advanced Backtesting Guide**: `docs/Advanced Concepts/vector-backtesting.md`
- **Parallel Processing Guide**: `docs/PARALLEL_PROCESSING_GUIDE.md`
- **Strategy Examples**: `examples/example_strategies/`

### Tips for Success

1. **Start Simple**: Begin with simple strategies before adding complexity
2. **Test Robustness**: A strategy that works across different parameters and time periods is more reliable
3. **Avoid Overfitting**: More parameters = higher risk of overfitting. Use permutation tests to validate
4. **Document Everything**: Keep track of your experiments and findings
5. **Be Patient**: Finding profitable strategies takes time and iteration
6. **Risk Management**: Always include stop-losses and position sizing in your final strategies

## 📧 Support

If you encounter issues or have questions:
- Check the main framework documentation
- Review the example strategies in `examples/example_strategies/`
- Open an issue on GitHub
- Join the community Discord/forum

## 📄 License

This tutorial is part of the Investing Algorithm Framework and is provided under the same license as the main framework.

---

**Happy Strategy Hunting! 🚀📈**

Remember: Past performance does not guarantee future results. Always test thoroughly and use proper risk management in live trading.

