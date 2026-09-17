---
sidebar_label: Monte Carlo Testing
---

# Monte Carlo Permutation Testing

Monte Carlo permutation testing estimates how unusual a strategy's observed
performance is relative to randomized market paths. The framework runs the
strategy on the original OHLCV data, permutes that data repeatedly, reruns the
same strategy, and compares the real metrics with the null distributions.

This is a statistical robustness check. It does not predict future returns or
replace out-of-sample and walk-forward validation.

## Run a test

Configure the app and strategy data providers as for a normal backtest, then
call `run_monte_carlo_test` with one date range:

```python
from investing_algorithm_framework import BacktestDateRange

date_range = BacktestDateRange(
    start_date=start_date,
    end_date=end_date,
    name="validation-window",
)

result = app.run_monte_carlo_test(
    strategy=strategy,
    backtest_date_range=date_range,
    number_of_permutations=1_000,
    initial_amount=10_000,
    market="BITVAVO",
    trading_symbol="EUR",
    risk_free_rate=0.027,
    show_progress=True,
)

result.compute_p_values()
print(result.summary())
```

The result contains the real metrics, metrics from every permuted run, and the
original and permuted OHLCV datasets. `compute_p_values()` populates its
metric-level p-values. Calling `summary()` computes the default one-sided
p-values lazily when needed.

## Metrics

The default set includes:

| Direction | Metrics |
| --- | --- |
| Higher is better | CAGR, Sharpe, Sortino, Calmar, profit factor, win rate, win/loss ratio, average monthly return |
| Lower is better | Annual volatility, maximum drawdown |

Pass a metric list to `compute_p_values(metrics=[...])` or `summary()` to focus
the analysis. Use `one_sided=False` when absolute deviations from zero in either
direction are relevant.

## Interpret p-values

For the default one-sided test, each p-value is an empirical tail probability.
For higher-is-better metrics, the framework computes:

`p = count(permuted >= observed) / number_of_permutations`

For lower-is-better metrics, it computes:

`p = count(permuted <= observed) / number_of_permutations`

A lower value means fewer randomized paths produced an equally strong result.
The probability is conditional on this permutation procedure and its market
data; it is not the probability that the strategy itself occurred "by chance."

With $N$ permutations, p-value resolution is limited to steps of $1/N$. One
hundred permutations therefore cannot distinguish values between 0.00 and 0.01.
A reported value of zero means no sampled permutation was at least as strong;
it does not establish an impossible event. Increase the count when decisions
require finer resolution, while accounting for the additional backtest cost.

Do not treat a low p-value as proof of a durable edge. Data leakage, parameter
selection, execution assumptions, regime changes, and repeated testing across
many candidates can still invalidate a result.

## Recommended workflow

1. Develop and filter candidates with vector backtests.
2. Validate execution behavior with event-driven backtests.
3. Reserve an untouched out-of-sample window.
4. Run permutation testing on the chosen evaluation protocol.
5. Confirm stability across rolling windows and realistic costs.

See [Backtesting](../Getting%20Started/backtesting.md),
[Vector Backtesting](../Getting%20Started/vector-backtesting.md), and
[Metrics](../Getting%20Started/metrics.md).