---
sidebar_position: 13
---

# Metrics Reference

The framework computes metrics at **two levels**:

1. **Per-run metrics** (`BacktestMetrics`): one set per individual
   backtest run / window. Includes everything specific to that run:
   the equity curve, drawdown series, monthly/yearly return tables,
   best/worst trade, exposure, etc.
2. **Summary metrics** (`BacktestSummaryMetrics`): a single roll-up
   across **all runs/windows** in a backtest. Used for ranking and
   robustness analysis in the [HTML report](./backtest-reports).

Both objects expose roughly the same headline stats (CAGR, Sharpe,
max drawdown, win rate…), but the per-run object is richer (it has
time-series like `equity_curve` and `drawdown_series`) while the
summary adds **multi-window** measures (`consistency_score`,
`stability_score`, `number_of_profitable_windows`).

Prefer the getters over direct attribute access — they handle missing
runs / metrics safely and work the same way whether the backtest was
just produced or loaded from an `.iafbt` bundle.

```python
from investing_algorithm_framework import BacktestDateRange

backtest = app.run_backtest(...)  # or app.run_vector_backtest(...)

# Cross-window roll-up
summary = backtest.get_backtest_summary()
print(f"CAGR:          {summary.cagr:.2%}")
print(f"Max drawdown:  {summary.max_drawdown:.2%}")

# Per-run details — one BacktestMetrics per run/window
for metrics in backtest.get_all_backtest_metrics():
    print(
        f"{metrics.backtest_date_range_name}: "
        f"return={metrics.total_net_gain_percentage:.2%}, "
        f"sharpe={metrics.sharpe_ratio:.2f}"
    )

# Or fetch a specific window by date range
date_range = BacktestDateRange(
    start_date="2022-01-01", end_date="2022-12-31", name="2022"
)
metrics = backtest.get_backtest_metrics(date_range)
run = backtest.get_backtest_run(date_range)
```

All metrics are persisted inside the `.iafbt` bundle, so reports
loaded from disk have identical values without recomputation.

## Conventions

- **Decimal vs percentage.** Fields ending in `_percentage` are decimals
  (e.g. `0.42` means 42%). Fields without a `_percentage` suffix are in
  account currency, except for ratios (Sharpe, Sortino, Calmar,
  win/loss, profit factor) which are dimensionless.
- **Currency**. All currency-denominated metrics are expressed in the
  portfolio's `trading_symbol` (typically EUR/USD/USDT).
- **Per-run vs per-trade**. On `BacktestMetrics`, `total_*` is over the
  whole run, `average_trade_*` is over closed trades within that run.
  On `BacktestSummaryMetrics`, `average_*` (without `trade_`) is the
  time-weighted mean **across windows**.
- **Single window**. If the backtest has only one window, summary
  `total_*` and `average_*` collapse to the corresponding per-run
  values by definition.
- **Annualization**. Sharpe, Sortino, CAGR, and annual volatility are
  annualized using the backtest's bar frequency (252 trading days for
  daily, scaled accordingly for intraday).

---

## Per-run metrics — `BacktestMetrics`

One `BacktestMetrics` instance is produced for every backtest run /
window. Retrieve them via `backtest.get_all_backtest_metrics()` or a
specific one via `backtest.get_backtest_metrics(date_range)`.

### Run identity

| Metric | Type | Description |
|---|---|---|
| `backtest_date_range_name` | str | Human-readable name of the date range (e.g. `"2022_bear"`). |
| `backtest_start_date` | datetime | First bar timestamp of the run. |
| `backtest_end_date` | datetime | Last bar timestamp of the run. |
| `total_number_of_days` | int | Calendar days covered by the run. |
| `trading_symbol` | str | Quote currency of the portfolio (e.g. `"EUR"`). |
| `initial_unallocated` | currency | Starting cash for the run. |
| `final_value` | currency | Portfolio value at the last bar. |
| `metadata` | dict | Free-form metadata attached to the run. |

### Returns and growth (per-run)

| Metric | Type | Description |
|---|---|---|
| `total_net_gain` | currency | `final_value − initial_unallocated`. |
| `total_net_gain_percentage` | decimal | `total_net_gain / initial_unallocated`. |
| `total_growth` / `total_growth_percentage` | currency / decimal | Legacy aliases of `total_net_gain*`. |
| `total_loss` | currency | Gross loss magnitude (sum of `abs(net_gain)` over losing trades). |
| `total_loss_percentage` | decimal | `total_loss / initial_unallocated`. |
| `gross_profit` | currency | Sum of P&L of winning trades. |
| `gross_loss` | currency | Sum of P&L of losing trades (negative). |
| `cumulative_return` | decimal | Cumulative return over the run. |
| `cagr` | decimal | Compound annual growth rate. |
| `annual_volatility` | decimal | Annualized stdev of periodic returns. |

### Time series (per-run only)

These are lists of `(value, datetime)` tuples used to render the charts
in the HTML dashboard.

| Metric | Type | Description |
|---|---|---|
| `equity_curve` | list[(float, datetime)] | Portfolio value over time. |
| `cumulative_return_series` | list[(float, datetime)] | Cumulative return over time. |
| `rolling_sharpe_ratio` | list[(float, datetime)] | Rolling Sharpe ratio over a fixed lookback. |
| `drawdown_series` | list[(float, datetime)] | Drawdown from running peak over time. |
| `monthly_returns` | list[(float, datetime)] | Monthly return per month. Powers the heatmap. |
| `yearly_returns` | list[(float, date)] | Yearly return per year. |

### Risk-adjusted performance (per-run)

| Metric | Type | Description |
|---|---|---|
| `sharpe_ratio` | ratio | Annualized excess return / annualized volatility. |
| `sortino_ratio` | ratio | Annualized excess return / downside deviation. |
| `calmar_ratio` | ratio | `cagr / max_drawdown`. |
| `profit_factor` | ratio | `gross_profit / abs(gross_loss)`. |

### Drawdown and tail risk (per-run)

| Metric | Type | Description |
|---|---|---|
| `max_drawdown` | decimal | Largest peak-to-trough drop, as a fraction of peak. |
| `max_drawdown_absolute` | currency | Same drop in account currency. |
| `max_daily_drawdown` | decimal | Largest single-day equity drop. |
| `max_drawdown_duration` | int (days) | Days from drawdown peak to recovery. |
| `var_95` | decimal | Value at Risk at 95% confidence. |
| `cvar_95` | decimal | Conditional VaR — average loss in the worst 5% of cases. |

### Trade statistics (per-run)

| Metric | Type | Description |
|---|---|---|
| `number_of_trades` | int | All trades touched during the run. |
| `number_of_trades_opened` | int | Trades opened during the run. |
| `number_of_trades_closed` | int | Trades closed during the run. |
| `number_of_trades_open_at_end` | int | Trades still open at last bar. |
| `number_of_positive_trades` | int | Profitable closed trades. |
| `number_of_negative_trades` | int | Losing closed trades. |
| `percentage_positive_trades` | decimal | `n_positive / n_closed`. |
| `percentage_negative_trades` | decimal | `n_negative / n_closed`. |
| `average_trade_size` | currency | Mean notional per trade. |
| `average_trade_return` / `_percentage` | currency / decimal | Mean P&L of all closed trades. |
| `median_trade_return` / `_percentage` | currency / decimal | Median P&L. |
| `average_trade_gain` / `_percentage` | currency / decimal | Mean P&L of winning trades. |
| `average_trade_loss` / `_percentage` | currency / decimal | Mean loss of losing trades. |
| `average_trade_duration` | hours | Mean time a trade is open. |
| `average_win_duration` | hours | Mean duration of winning trades. |
| `average_loss_duration` | hours | Mean duration of losing trades. |
| `best_trade` | Trade | Highest-P&L trade in the run. |
| `worst_trade` | Trade | Lowest-P&L trade in the run. |
| `current_average_trade_*` | various | Same as above but rolling over the most recent trades. |

### Win/loss (per-run)

| Metric | Type | Description |
|---|---|---|
| `win_rate` | decimal | `n_positive / n_closed`. |
| `current_win_rate` | decimal | Rolling win rate over recent trades. |
| `win_loss_ratio` | ratio | `average_trade_gain / average_trade_loss`. |
| `current_win_loss_ratio` | ratio | Rolling version. |
| `max_consecutive_wins` | int | Longest winning streak. |
| `max_consecutive_losses` | int | Longest losing streak. |

### Calendar performance (per-run)

| Metric | Type | Description |
|---|---|---|
| `percentage_winning_months` | decimal | Months with positive return / total months. |
| `percentage_winning_years` | decimal | Years with positive return / total years. |
| `average_monthly_return` | decimal | Mean monthly return. |
| `average_monthly_return_winning_months` | decimal | Mean return over positive months. |
| `average_monthly_return_losing_months` | decimal | Mean return over negative months. |
| `best_month` | (float, datetime) | Best monthly return. |
| `worst_month` | (float, datetime) | Worst monthly return. |
| `best_year` | (float, date) | Best yearly return. |
| `worst_year` | (float, date) | Worst yearly return. |

### Exposure and activity (per-run)

| Metric | Type | Description |
|---|---|---|
| `cumulative_exposure` | currency × time | Integral of capital deployed. |
| `exposure_ratio` | decimal | Fraction of time with at least one open position. |
| `trades_per_year` | float | Annualized trade frequency. |
| `trades_per_month` | float | Monthly trade frequency. |
| `trades_per_week` | float | Weekly trade frequency. |
| `trade_per_day` | float | Daily trade frequency. |

---

## Summary metrics — `BacktestSummaryMetrics`

A single roll-up across **all runs/windows** in a backtest. Available
via `backtest.get_backtest_summary()`. Used by `BacktestReport` for
ranking, filtering, and KPI cards.

For single-window backtests these collapse to the per-run values; for
multi-window backtests (e.g. walk-forward, permutation tests, see
[Vector Backtesting](./vector-backtesting)) they aggregate across
windows and add robustness measures.

### Returns and growth (aggregate)

| Metric | Type | Description |
|---|---|---|
| `total_net_gain` | currency | Sum of per-window net gains. |
| `total_net_gain_percentage` | decimal | `total_net_gain` / total initial capital. |
| `total_growth` / `total_growth_percentage` | currency / decimal | Legacy aliases of `total_net_gain*`. |
| `cagr` | decimal | Compound annual growth rate of the combined equity curve. |
| `annual_volatility` | decimal | Annualized return volatility across windows. |
| `average_net_gain` / `_percentage` | currency / decimal | Time-weighted mean per-window net gain. |
| `average_growth` / `_percentage` | currency / decimal | Legacy aliases. |

### Risk-adjusted performance (aggregate)

| Metric | Type | Description |
|---|---|---|
| `sharpe_ratio` | ratio | Annualized excess return / annualized volatility. |
| `sortino_ratio` | ratio | Downside-risk adjusted return. |
| `calmar_ratio` | ratio | `cagr / max_drawdown`. |
| `profit_factor` | ratio | Gross profit / gross loss across all closed trades. |

### Drawdown and tail risk (aggregate)

| Metric | Type | Description |
|---|---|---|
| `max_drawdown` | decimal | Worst peak-to-trough drop seen across all windows. |
| `max_drawdown_duration` | int (bars) | Bars between the worst drawdown peak and recovery. |
| `var_95` | decimal | Value at Risk at 95% confidence across all returns. |
| `cvar_95` | decimal | Conditional VaR. |

### Loss metrics (aggregate)

| Metric | Type | Description |
|---|---|---|
| `total_loss` | currency | Sum of per-window gross losses (non-negative magnitude). |
| `total_loss_percentage` | decimal | `total_loss` / total initial capital. |
| `average_loss` / `_percentage` | currency / decimal | Time-weighted mean loss across windows. |

### Per-trade metrics (aggregate)

| Metric | Type | Description |
|---|---|---|
| `number_of_trades` | int | Trades opened across all windows. |
| `number_of_trades_closed` | int | Trades closed across all windows. |
| `average_trade_return` / `_percentage` | currency / decimal | Mean P&L per closed trade. |
| `average_trade_gain` / `_percentage` | currency / decimal | Mean P&L of winners. |
| `average_trade_loss` / `_percentage` | currency / decimal | Mean loss of losers. |
| `average_trade_duration` | seconds | Mean trade open time. |
| `average_win_duration` | seconds | Mean winning trade duration. |
| `average_loss_duration` | seconds | Mean losing trade duration. |

### Win/loss statistics (aggregate)

| Metric | Type | Description |
|---|---|---|
| `win_rate` | decimal | Profitable trades / closed trades across all windows. |
| `current_win_rate` | decimal | Rolling win rate over recent trades. |
| `win_loss_ratio` | ratio | `average_trade_gain` / `average_trade_loss`. |
| `current_win_loss_ratio` | ratio | Rolling version. |
| `max_consecutive_wins` | int | Longest winning streak across all windows. |
| `max_consecutive_losses` | int | Longest losing streak across all windows. |

### Exposure and activity (aggregate)

| Metric | Type | Description |
|---|---|---|
| `cumulative_exposure` | currency × time | Total capital deployed across all windows. |
| `exposure_ratio` | decimal | Fraction of time with at least one open position. |
| `trades_per_year` / `trades_per_month` / `trades_per_week` | float | Annualized / monthly / weekly trade frequency. |

### Multi-window robustness (summary-only)

These metrics only exist on `BacktestSummaryMetrics` — they describe
how performance varies *across* windows and have no per-run analog.

| Metric | Type | Description |
|---|---|---|
| `number_of_windows` | int | Total backtest windows executed. |
| `number_of_windows_with_trades` | int | Windows in which at least one trade closed. |
| `number_of_profitable_windows` | int | Windows with positive net gain. |
| `return_consistency` | decimal | Coefficient of variation of per-window returns (lower = more consistent). |
| `win_rate_consistency` | decimal | Coefficient of variation of per-window win rates. |
| `sharpe_consistency` | decimal | Coefficient of variation of per-window Sharpe ratios. |
| `consistency_score` | decimal | Composite of the three `*_consistency` measures, scaled to `[0, 1]` (higher = better). |
| `return_stability` | decimal | Per-window return autocorrelation — how stable returns are over time. |
| `win_rate_stability` | decimal | Same, for win rate. |
| `sharpe_stability` | decimal | Same, for Sharpe ratio. |
| `stability_score` | decimal | Composite stability score, scaled to `[0, 1]` (higher = better). |

---

## Using metrics in code

Every summary metric is also available as a ranking key in
[`BacktestReport`](./backtest-reports):

```python
from investing_algorithm_framework import BacktestReport

report = BacktestReport.open(directory_path="backtest_results/")

# Top 10 strategies by Sharpe ratio
top_sharpe = report.rank(by="sharpe_ratio", ascending=False, limit=10)

# Filter to robust strategies only
robust = report.filter(
    lambda b: b.backtest_summary.consistency_score > 0.7
    and b.backtest_summary.max_drawdown < 0.2
)

# Drill into per-run detail for a specific backtest
for metrics in robust[0].get_all_backtest_metrics():
    print(f"{metrics.backtest_date_range_name}: {metrics.total_net_gain_percentage:.2%}")
```

For multi-strategy comparison and visualization, see
[Backtest Reports](./backtest-reports).
