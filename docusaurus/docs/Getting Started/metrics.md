---
sidebar_position: 13
---

# Backtest Metrics

The framework records more than 80 scalar measurements for each backtest run,
covering returns, risk, drawdowns, trades, exposure, and execution quality. It
also stores chart-ready series and a 55-field summary for comparing performance
across windows.

Metrics are calculated at two levels:

| Level | Object | Use it for |
| --- | --- | --- |
| Per run | `BacktestMetrics` | Inspecting one backtest window in detail. |
| Per study and engine | `BacktestSummaryMetrics` | Ranking strategies and judging consistency across windows. |

Both are persisted in the [Open Backtest Format](open-backtest-format). Opening
an `.obtf` bundle restores the recorded values without recomputing them.

## Access metrics

Results belong to a named study and an engine slot. Select those explicitly when
a bundle contains more than one study or both vector and event results:

```python
results = app.run_backtest(strategy=strategy, study=study)
backtest = next(results.iter_backtests())

completed_study = backtest.get_study(study.name)
summary = completed_study.get_summary(engine="vector")

for run in completed_study.get_runs(engine="vector"):
    metrics = run.backtest_metrics
    print(
        run.backtest_start_date,
        metrics.total_net_gain_percentage,
        metrics.sharpe_ratio,
        metrics.max_drawdown,
    )
```

Retrieve one known window directly through the study:

```python
metrics = completed_study.get_metrics(
    engine="vector",
    backtest_window=completed_study.backtest_windows[0],
)
```

For compatibility with single-study workflows, `Backtest` also provides
`get_backtest_metrics(...)` and `get_all_backtest_metrics()`.

## Value conventions

- Percentage fields are decimals: `0.12` means 12%.
- Currency values use the universe's trading symbol, such as EUR or USD.
- Durations on per-run metrics are hours unless noted otherwise.
- Ratios such as Sharpe, Sortino, Calmar, Omega, and profit factor are
  dimensionless.
- A missing or inapplicable value may be `None`, `NaN`, or zero depending on the
  metric and available observations. Check before ranking or formatting.
- `total_growth` and `total_growth_percentage` are legacy aliases for
  `total_net_gain` and `total_net_gain_percentage`.

## Per-run metrics

One `BacktestMetrics` object is attached to every completed run. The tables
below cover all current fields and derived identity properties.

### Identity and portfolio value

| Fields | Meaning |
| --- | --- |
| `backtest_window` | Persisted window definition that produced the run. |
| `backtest_start_date`, `backtest_end_date`, `backtest_date_range_name`, `window_role` | Derived identity of the active train or test range. |
| `total_number_of_days` | Calendar duration of the active range. |
| `initial_unallocated`, `final_value` | Starting cash and final portfolio value. |
| `metadata` | Free-form run metadata. |

### Returns and risk-adjusted performance

| Fields | Meaning |
| --- | --- |
| `total_net_gain`, `total_net_gain_percentage` | Net change in portfolio value. |
| `total_growth`, `total_growth_percentage` | Legacy aliases for total net gain. |
| `total_loss`, `total_loss_percentage` | Gross loss magnitude and its share of starting capital. |
| `gross_profit`, `gross_loss` | Sum of winning and losing trade P&L. |
| `cumulative_return`, `cagr` | Total compounded return and annualized growth. |
| `annual_volatility` | Annualized variability of periodic returns. |
| `sharpe_ratio` | Excess return relative to total volatility. |
| `sortino_ratio` | Excess return relative to downside volatility. |
| `calmar_ratio` | CAGR relative to maximum drawdown. |
| `omega_ratio` | Probability-weighted gains relative to losses. |
| `profit_factor` | Gross profit divided by gross loss magnitude. |
| `ulcer_index` | Depth and duration of percentage drawdowns. |
| `var_95`, `cvar_95` | Value at Risk and average loss beyond VaR at 95% confidence. |

### Drawdown and time series

| Fields | Meaning |
| --- | --- |
| `max_drawdown`, `max_drawdown_absolute` | Largest peak-to-trough loss as a decimal and currency value. |
| `max_daily_drawdown` | Largest one-day decline. |
| `max_drawdown_duration` | Duration of the longest maximum-drawdown episode. |
| `twr_max_drawdown`, `twr_max_drawdown_duration` | Drawdown after removing the effect of external cash flows. |
| `equity_curve`, `cumulative_return_series` | Portfolio value and cumulative return over time. |
| `rolling_sharpe_ratio`, `drawdown_series` | Rolling risk-adjusted return and drawdown over time. |
| `twr_equity_curve`, `twr_drawdown_series` | Time-weighted series that remove deposits and withdrawals. |
| `monthly_returns`, `yearly_returns` | Calendar return series used by reports and heatmaps. |

Use the time-weighted fields when comparing portfolios with different deposit
or withdrawal schedules. Raw equity and drawdown fields remain useful for
account-value reporting.

### Trade counts and direction

| Fields | Meaning |
| --- | --- |
| `number_of_trades`, `number_of_trades_opened`, `number_of_trades_closed`, `number_of_trades_open_at_end` | Overall trade activity and end state. |
| `number_of_positive_trades`, `number_of_negative_trades` | Winning and losing closed trades. |
| `percentage_positive_trades`, `percentage_negative_trades` | Winner and loser shares. |
| `number_of_long_trades`, `number_of_long_trades_closed` | Long trades opened and closed. |
| `number_of_winning_long_trades`, `number_of_losing_long_trades`, `long_win_rate` | Long-side outcomes. |
| `number_of_short_trades`, `number_of_short_trades_closed` | Short trades opened and closed. |
| `number_of_winning_short_trades`, `number_of_losing_short_trades`, `short_win_rate` | Short-side outcomes. |
| `best_trade`, `worst_trade` | Full trade objects for the strongest and weakest outcomes. |

### Trade returns, timing, and streaks

| Fields | Meaning |
| --- | --- |
| `average_trade_size` | Mean trade notional. |
| `average_trade_return`, `average_trade_return_percentage` | Mean P&L across closed trades. |
| `median_trade_return`, `median_trade_return_percentage` | Median P&L across closed trades. |
| `average_trade_gain`, `average_trade_gain_percentage` | Mean winning-trade P&L. |
| `average_trade_loss`, `average_trade_loss_percentage` | Mean losing-trade P&L. |
| `average_trade_duration`, `average_win_duration`, `average_loss_duration` | Mean holding periods overall, for winners, and for losers. |
| `current_average_trade_gain`, `current_average_trade_gain_percentage` | Recent average gain. |
| `current_average_trade_loss`, `current_average_trade_loss_percentage` | Recent average loss. |
| `current_average_trade_return`, `current_average_trade_return_percentage` | Recent average return. |
| `current_average_trade_duration` | Recent average holding period. |
| `win_rate`, `current_win_rate` | Overall and recent winner shares. |
| `win_loss_ratio`, `current_win_loss_ratio` | Overall and recent average win/loss ratios. |
| `max_consecutive_wins`, `max_consecutive_losses` | Longest winning and losing streaks. |

### Excursion, exposure, and activity

| Fields | Meaning |
| --- | --- |
| `average_mae`, `average_mae_percentage` | Mean maximum adverse excursion per trade. |
| `average_mfe`, `average_mfe_percentage` | Mean maximum favorable excursion per trade. |
| `max_mae`, `max_mfe` | Largest adverse and favorable excursions. |
| `mfe_mae_ratio` | Favorable excursion relative to adverse excursion. |
| `cumulative_exposure`, `exposure_ratio` | Capital deployed over time and fraction of time exposed. |
| `trades_per_year`, `trades_per_month`, `trades_per_week`, `trade_per_day` | Annualized and calendar-normalized trading frequency. |

### Calendar performance

| Fields | Meaning |
| --- | --- |
| `percentage_winning_months`, `percentage_winning_years` | Share of profitable calendar periods. |
| `average_monthly_return` | Mean monthly return. |
| `average_monthly_return_winning_months`, `average_monthly_return_losing_months` | Mean return split by profitable and losing months. |
| `best_month`, `worst_month`, `best_year`, `worst_year` | Return and date for calendar extremes. |

## Summary metrics

`BacktestSummaryMetrics` rolls up all runs in one study and engine slot. It has
55 fields: familiar return, risk, trade, and exposure measures plus
cross-window robustness statistics.

### Aggregate performance

| Fields | Meaning |
| --- | --- |
| `total_net_gain`, `total_net_gain_percentage`, `average_net_gain`, `average_net_gain_percentage` | Total and average net performance across windows. |
| `total_growth`, `total_growth_percentage`, `average_growth`, `average_growth_percentage` | Legacy growth aliases. |
| `total_loss`, `total_loss_percentage`, `average_loss`, `average_loss_percentage` | Total and average gross-loss magnitude. |
| `cagr`, `annual_volatility` | Annualized growth and volatility. |
| `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `profit_factor` | Aggregate risk-adjusted and payoff ratios. |
| `max_drawdown`, `max_drawdown_duration`, `var_95`, `cvar_95` | Aggregate drawdown and tail risk. |

### Aggregate trades and exposure

| Fields | Meaning |
| --- | --- |
| `number_of_trades`, `number_of_trades_closed` | Total trade activity. |
| `average_trade_return`, `average_trade_return_percentage` | Mean closed-trade P&L. |
| `average_trade_gain`, `average_trade_gain_percentage` | Mean winner. |
| `average_trade_loss`, `average_trade_loss_percentage` | Mean loser. |
| `average_trade_duration`, `average_win_duration`, `average_loss_duration` | Aggregate holding periods. |
| `win_rate`, `current_win_rate`, `win_loss_ratio`, `current_win_loss_ratio` | Overall and recent win/loss quality. |
| `max_consecutive_wins`, `max_consecutive_losses` | Longest streaks. |
| `cumulative_exposure`, `exposure_ratio` | Aggregate capital deployment. |
| `trades_per_year`, `trades_per_month`, `trades_per_week` | Normalized trading frequency. |

### Cross-window robustness

| Fields | Meaning |
| --- | --- |
| `number_of_windows` | Runs included in the summary. |
| `number_of_windows_with_trades` | Windows with at least one closed trade. |
| `number_of_profitable_windows` | Windows with positive net gain. |
| `return_consistency`, `win_rate_consistency`, `sharpe_consistency` | Variation of each measure across windows; lower is more consistent. |
| `consistency_score` | Combined consistency score from 0 to 1; higher is better. |
| `return_stability`, `win_rate_stability`, `sharpe_stability` | Persistence of each measure across ordered windows. |
| `stability_score` | Combined stability score from 0 to 1; higher is better. |

Consistency asks whether windows produce similar outcomes. Stability asks
whether those outcomes persist in order. Use both alongside the number of
profitable windows; none should replace inspection of individual runs.

## Rank and filter

`BacktestIndex` promotes summary values to scalar columns, allowing large result
sets to be filtered without loading every bundle:

```python
import pandas as pd

# Keep pooled rows, then require acceptable risk and repeatability.
candidates = results.filter(lambda row: (
    pd.isna(row["universe_key"])
    and row["summary.sharpe_ratio"] >= 1.0
    and row["summary.max_drawdown"] <= 0.20
    and row["summary.consistency_score"] >= 0.70
))

leader_ids = set(
  candidates.df
  .sort_values("summary.sharpe_ratio", ascending=False)
  .head(20)["algorithm_id"]
)
leaders = candidates.filter(
  lambda row: row["algorithm_id"] in leader_ids
)

for backtest in leaders.iter_backtests():
  print(backtest.algorithm_id)
```

After selecting candidates, load their full bundles and inspect per-window
metrics, trades, and equity curves. See [Backtest Reports](backtest-reports) for
interactive comparison and [Backtest Storage](backtest-storage) for SQLite
indexing across large collections.

## How the 80+ count is defined

`BacktestMetrics` currently has 105 dataclass fields. The public `80+` claim is
deliberately conservative: it excludes the window identity, metadata, chart
series, rich trade/calendar objects, and legacy growth aliases, leaving more
than 80 scalar per-run measurements. The 55 summary fields are a separate
cross-window view and are not added to that claim.