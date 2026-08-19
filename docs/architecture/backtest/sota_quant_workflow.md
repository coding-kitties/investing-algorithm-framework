# State-of-the-Art Quantitative Backtesting Workflow

A reference specification for a rigorous, bias-aware backtesting
pipeline. Each section describes **what** a SOTA workflow requires,
**why** it matters, and the framework's current status.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase 1 — Data Foundation](#2-phase-1--data-foundation)
3. [Phase 2 — Signal Development](#3-phase-2--signal-development)
4. [Phase 3 — In-Sample Exploration](#4-phase-3--in-sample-exploration)
5. [Phase 4 — Statistical Debiasing](#5-phase-4--statistical-debiasing)
6. [Phase 5 — Out-of-Sample Validation](#6-phase-5--out-of-sample-validation)
7. [Phase 6 — Execution Fidelity](#7-phase-6--execution-fidelity)
8. [Phase 7 — Robustness & Significance](#8-phase-7--robustness--significance)
9. [Phase 8 — Portfolio Construction](#9-phase-8--portfolio-construction)
10. [Phase 9 — Production Readiness](#10-phase-9--production-readiness)
11. [Anti-Patterns](#11-anti-patterns)
12. [References](#12-references)

---

## 1. Overview

A backtest that produces a high Sharpe ratio proves nothing by
itself. The question is not "does my strategy look good in
hindsight?" but "what is the probability that this result would
occur under the null hypothesis of no skill, given the number of
configurations I tested?"

A SOTA pipeline is organised around three goals:

1. **Maximise the out-of-sample predictive power** of the in-sample
   selection by controlling for overfitting, selection bias, and
   multiple testing.
2. **Minimise the gap between simulation and reality** through
   realistic execution modelling, regime-aware evaluation, and
   stress testing.
3. **Produce a quantified confidence level** — not a subjective
   "this looks good" but a p-value, a probability of backtest
   overfitting, and a measured IS→OOS decay ratio.

```
Phase 1   Data Foundation
            │
Phase 2   Signal Development (visualise, understand)
            │
Phase 3   In-Sample Exploration (grid search, walk-forward)
            │
Phase 4   Statistical Debiasing (deflated Sharpe, CPCV/PBO)
            │
Phase 5   Out-of-Sample Validation (time OOS + universe OOS)
            │
Phase 6   Execution Fidelity (event engine, slippage, impact)
            │
Phase 7   Robustness & Significance (Monte Carlo, SPA, regime)
            │
Phase 8   Portfolio Construction (sizing, correlation, risk)
            │
Phase 9   Production Readiness (monitoring, kill switches)
```

---

## 2. Phase 1 — Data Foundation

### Requirements

| Requirement | Rationale |
|---|---|
| Multiple timeframes | Strategies often combine trend filters on higher timeframes with entries on lower timeframes |
| Gap detection and filling | Missing bars create phantom signals and distort indicator calculations |
| Regime characterisation | Know *what* your data covers before you test on it — a strategy tested only in a bull market has not been tested |
| Survivorship-bias-free universe | If you only include assets that exist today, you overstate returns |
| Sufficient history | Rule of thumb: 10× the longest lookback period, across ≥ 2 full market cycles |

### Framework Status

| Feature | Status |
|---|---|
| `download_v2()` — declarative multi-symbol, multi-timeframe download | Implemented |
| `fill_missing_timeseries_data()` / `get_missing_timeseries_data_entries()` | Implemented |
| `analyze_backtest_windows()` — per-window regime stats (return, vol, Sharpe, Hurst, skew, kurtosis, regime label) | Implemented |
| `plot_backtest_windows()` / `plot_window_correlation_matrix()` | Implemented |
| Survivorship-bias correction | Not implemented — user responsibility to curate the universe |

---

## 3. Phase 2 — Signal Development

### Requirements

Before running any sweep, visually verify that the strategy's
signal logic behaves as intended on a single window. This catches
look-ahead bugs, indicator miscalculations, and rule-ordering
errors that no amount of grid search can fix.

- Plot indicator values alongside price
- Overlay buy/sell signal markers
- Verify stop-loss, take-profit, and cooldown behaviour
- Check that no future data leaks into signal generation

### Framework Status

| Feature | Status |
|---|---|
| `app.run_backtest(strategy=..., study=Study(engines=[BacktestEngine.VECTOR]))` — single-window, single-strategy | Implemented |
| `backtest.get_backtest_run()` — extract trades, orders, signals | Implemented |
| Signal series in `BacktestRun.signals` and `BacktestRun.signal_events` | Implemented |
| `BacktestRun.recorded_values` — custom indicator snapshots | Implemented |
| Look-ahead detection tooling | Not implemented — user responsibility |

---

## 4. Phase 3 — In-Sample Exploration

### Requirements

| Requirement | Rationale |
|---|---|
| Walk-forward rolling windows | Avoids the single-split problem. Each window is a pseudo-OOS test for the windows that came before it |
| Progressive pruning | Kills weak candidates early, saving compute and reducing the effective number of trials |
| Deterministic algorithm fingerprinting | Ensures bundle lineage is preserved across notebooks — OOS results land in the same file |
| Consistency and stability metrics | A strategy that wins big on one window and loses on three is not the same as one that wins modestly on all four |

### Walk-Forward Design

```
Window 1:  |---train---|--gap--|---test---|
Window 2:       |---train---|--gap--|---test---|
Window 3:            |---train---|--gap--|---test---|
   ...
```

- **Train**: the window the strategy runs on
- **Gap**: purging period to prevent information leakage between
  adjacent windows (typically 1–2× the strategy's maximum lookback)
- **Test**: reserved for later OOS analysis (not used in-sample)

### Progressive Pruning

Two-layer filter applied between windows:

1. **Per-window gate**: did the strategy produce at least N closed
   trades? (activity check)
2. **Cross-window gate** (after warmup): is the running track
   record consistent? (≥ 50% windows profitable, positive
   aggregate PnL, acceptable drawdown)

The pruning ratio compounds across windows. A 96-combination grid
across 10 windows with 50% survival per window reduces total runs
from 960 to ~300.

### Ranking

Multi-metric weighted scoring with configurable focus:

| Focus | Emphasis |
|---|---|
| `BALANCED` | Sharpe, net gain, win rate, consistency, stability |
| `PROFIT` | Net gain, CAGR, profit factor |
| `FREQUENCY` | Trade count, trades/year, win rate |
| `RISK_ADJUSTED` | Sharpe, Sortino, max drawdown penalty, consistency, stability |

Scoring normalises each metric to [0, 1] across the candidate set,
multiplies by the weight, and sums. This is a relative ranking —
it tells you which candidates are best *among those tested*, not
whether any of them are good in absolute terms. That is what
Phase 4 addresses.

### Framework Status

| Feature | Status |
|---|---|
| `generate_rolling_backtest_windows()` with train/gap/test splits | Implemented |
| `app.run_backtests()` with `window_filter_function` | Implemented |
| `generate_algorithm_id(params=...)` — deterministic fingerprint | Implemented |
| `rank_results()` — in-memory weighted scoring | Implemented |
| `build_index()` / `rank_index()` — Tier-1 SQLite millisecond ranking | Implemented |
| `promote_backtests()` — copy winners to a clean folder | Implemented |
| Consistency/stability metrics on `BacktestSummaryMetrics` | Implemented |
| Checkpointing (`use_checkpoints=True`) | Implemented |
| Parallel execution (`n_workers`) | Implemented |

---

## 5. Phase 4 — Statistical Debiasing

This is the phase most practitioners skip and the one that matters
most. Without it, you cannot distinguish skill from luck.

### 5.1 The Multiple Testing Problem

If you test N parameter combinations, the expected maximum Sharpe
ratio under the null hypothesis (no skill, pure noise) is:

$$E[\max(SR)] \approx \sqrt{2 \cdot \ln(N)}$$

For N = 96: $E[\max(SR)] \approx 3.02$

This means a Sharpe of 3.0 from a 96-combination sweep is
**completely explained by chance**. You have not found a strategy —
you have found the best random walk out of 96.

### 5.2 Deflated Sharpe Ratio (DSR)

The Deflated Sharpe Ratio (Bailey & López de Prado, 2014) adjusts
the observed Sharpe for the number of trials, the skewness and
kurtosis of returns, and the length of the track record:

$$DSR = \Phi\left(\frac{(\widehat{SR} - SR_0) \cdot \sqrt{T-1}}{\sqrt{1 - \hat{\gamma}_3 \cdot \widehat{SR} + \frac{\hat{\gamma}_4 - 1}{4} \cdot \widehat{SR}^2}}\right)$$

Where:
- $\widehat{SR}$ is the observed Sharpe ratio
- $SR_0 = \sqrt{2 \cdot \ln(N)}$ is the expected maximum Sharpe under the null
- $T$ is the number of return observations
- $\hat{\gamma}_3$ is the skewness of returns
- $\hat{\gamma}_4$ is the kurtosis of returns
- $\Phi$ is the standard normal CDF

DSR returns a probability in [0, 1]. A DSR of 0.95 means there is
a 95% chance the observed Sharpe is not explained by multiple
testing. **This should be computed in the ranking step**, not after
the fact.

### 5.3 Probability of Backtest Overfitting (PBO)

PBO (Bailey et al., 2017) uses Combinatorial Purged
Cross-Validation (CPCV) to estimate the probability that the
in-sample winner will underperform the median out-of-sample:

1. Partition the data into S subsets
2. For each combination of S/2 subsets as training and S/2 as
   testing (with purging between adjacent subsets):
   - Select the best strategy in-sample
   - Record its OOS rank (relative to all other strategies)
3. PBO = fraction of combinations where the IS winner ranks below
   the OOS median

A PBO of 0.5 means you are coin-flipping. A PBO above 0.4 should
give you serious pause. Below 0.2 is encouraging.

CPCV is a superset of walk-forward validation — it uses **all
possible** train/test partitions (with purging), not just the
chronological ones. This gives a more complete estimate of
overfitting probability.

### 5.4 Minimum Track Record Length (MinTRL)

Given a target Sharpe $SR^*$ and the observed Sharpe $\widehat{SR}$
with return skewness $\hat{\gamma}_3$ and kurtosis $\hat{\gamma}_4$:

$$MinTRL = 1 + \left(1 - \hat{\gamma}_3 \cdot \widehat{SR} + \frac{\hat{\gamma}_4 - 1}{4} \cdot \widehat{SR}^2\right) \cdot \left(\frac{z_\alpha}{\widehat{SR} - SR^*}\right)^2$$

This tells you how many observations you need before the observed
Sharpe becomes statistically significant. If MinTRL exceeds your
actual track record, you do not have enough data to draw
conclusions.

### Framework Status

| Feature | Status |
|---|---|
| Deflated Sharpe Ratio in `rank_results()` / `rank_index()` | **Not implemented** — highest-priority gap |
| PBO via CPCV | **Not implemented** — can be done as a study using existing window infrastructure |
| MinTRL | **Not implemented** — closed-form, easy to add |
| Number of trials tracked per sweep | **Not tracked** — needed as input to DSR |

---

## 6. Phase 5 — Out-of-Sample Validation

### Requirements

Two independent OOS axes, neither of which was used during
in-sample selection:

| Axis | What it tests | Example |
|---|---|---|
| **Time OOS** | Temporal robustness — does the edge survive a different market regime? | In-sample 2022–2025 → OOS 2019–2021 |
| **Universe OOS** | Symbol robustness — does the edge generalise to different assets? | In-sample BTC/ETH/ADA/SOL/DOT → OOS LINK/AVAX/ATOM/ALGO/XRP |

### IS→OOS Decay Ratio

The single most informative diagnostic:

$$\text{decay} = \frac{SR_{OOS}}{SR_{IS}}$$

| Decay | Interpretation |
|---|---|
| > 0.8 | Excellent — minimal overfitting |
| 0.5 – 0.8 | Acceptable — some parameter fitting, but edge likely real |
| 0.2 – 0.5 | Concerning — significant overfitting |
| < 0.2 | Strategy is likely curve-fit to in-sample data |

Compute this separately for time-OOS and universe-OOS. A strategy
with high time-OOS decay but low universe-OOS decay has an edge
that is real but asset-specific.

### Bundle Lineage

OOS results should land in the **same bundle** as in-sample results
(matched by `algorithm_id` hash). This keeps all evidence for one
parameter combination together and enables cross-study comparison
without file juggling.

### Framework Status

| Feature | Status |
|---|---|
| Time OOS and Universe OOS studies | Implemented (tutorial notebooks 04) |
| Bundle lineage via deterministic `algorithm_id` | Implemented |
| Multi-study bundles (IS + OOS in one `.iafbt` file) | Implemented |
| IS→OOS decay ratio metric | **Not implemented** — trivial to add as a notebook analysis |

---

## 7. Phase 6 — Execution Fidelity

### Requirements

A strategy that works under instantaneous, costless execution but
fails under realistic trading conditions is not a strategy — it is
a simulation artifact.

| Requirement | Rationale |
|---|---|
| Bar-by-bar order routing | Strategies that rely on same-bar execution of signals have a timing assumption that won't hold live |
| Realistic fill model | Market orders fill at open, limits check against high/low, stops trigger then fill |
| Fee model | Fixed + percentage fees per trade |
| Slippage model | Price impact from the act of trading itself |
| Volume-based partial fills | You cannot fill 100% of a thin market's daily volume |
| Capital tracking | Position sizing must reflect actual available capital, not theoretical |

### Fill Model Hierarchy

The framework supports three levels of execution realism:

1. **Zero-cost** (default): no fees, no slippage — useful only for
   signal development, never for validation
2. **TradingCost**: flat fee + percentage fee + fixed or
   percentage-based slippage — sufficient for liquid large-cap
   markets
3. **Blotter**: pluggable `get_fill_price()`, `get_fill_amount()`,
   `on_fill()` — supports custom market-impact models like
   Almgren-Chriss or volume-share-of-day

### Market Impact

For mid-cap and small-cap assets, market impact is the dominant
cost. A percentage-of-volume slippage model is the minimum:

$$\text{slippage} = \eta \cdot \sigma \cdot \left(\frac{Q}{V}\right)^\beta$$

Where $Q$ is order size, $V$ is daily volume, $\sigma$ is
volatility, and $\eta$, $\beta$ are calibrated constants. The
framework's `VolumeShareSlippage` model supports this pattern.

### Vector vs. Event Comparison

Running the same study under both engines and comparing results is
a powerful diagnostic:

| Signal | Meaning |
|---|---|
| Vector ≈ Event | Signal timing is not critical; strategy is robust to execution |
| Vector >> Event | Strategy depends on same-bar fills or unrealistic timing |
| Vector << Event | Unlikely but possible — event engine captures intra-bar dynamics that benefit the strategy |

### Framework Status

| Feature | Status |
|---|---|
| Event engine with bar-by-bar order routing | Implemented |
| Market/limit/stop/stop-limit fill simulation | Implemented |
| `TradingCost` with fee + slippage percentage | Implemented |
| `VolumeShareSlippage` / `FixedBasisPointsSlippage` | Implemented |
| Blotter interface for custom fill models | Implemented |
| Partial fills with volume constraints | Implemented |
| Dual-engine bundles (vector + event in same file) | Implemented |
| Almgren-Chriss market impact model | Not implemented — can be added via Blotter interface |

---

## 8. Phase 7 — Robustness & Significance

### 8.1 Monte Carlo Permutation Tests

Destroy the temporal structure of the data while preserving its
distributional properties, then re-run the strategy. If the
strategy still "works" on shuffled data, it was never working — it
was fitting noise.

**Method**: Return-shuffle the OHLCV data, re-run the strategy N
times (typically 100–1000), compute a p-value as the fraction of
permuted runs that match or exceed the real result.

| p-value | Interpretation |
|---|---|
| < 0.01 | Strong evidence of genuine edge |
| 0.01 – 0.05 | Moderate evidence |
| 0.05 – 0.10 | Weak evidence — proceed with caution |
| > 0.10 | Cannot reject the null — the result is consistent with chance |

### 8.2 Familywise Significance (White's Reality Check / Hansen's SPA)

Standard Monte Carlo tests one strategy at a time. But you selected
this strategy *because* it was the best out of N. The familywise
test asks: "is the **best** strategy significantly better than
chance, given that I tried N?"

- **White's Reality Check** (2000): bootstraps the performance
  differentials of all N strategies simultaneously. The p-value
  reflects the probability that the best strategy's advantage over
  zero is spurious.
- **Hansen's Superior Predictive Ability** (2005): refinement that
  uses a studentised statistic, giving more power against
  alternatives where only a few strategies are truly skilled.

### 8.3 Regime-Conditional Evaluation

A strategy that works on average but fails in the regime you are
currently in is useless. Regime-conditional evaluation requires:

1. **Tagging each run with its regime** (bull, bear, sideways,
   high-vol, low-vol)
2. **Filtering metrics by regime** — what is the Sharpe in bear
   markets only? What is the max drawdown in high-vol regimes?
3. **Conditional ranking** — rank strategies within each regime
   separately

The framework already labels regimes in
`analyze_backtest_windows()`. The gap is carrying those labels
through to `BacktestRun` so they can be queried at ranking time.

### 8.4 Stress Testing

Beyond historical regimes, synthesise adversarial scenarios:

- **Volatility shock**: scale returns by 2–3× for a period
- **Liquidity crisis**: reduce available volume by 80%
- **Correlation breakdown**: shuffle cross-asset correlations
- **Gap risk**: insert overnight gaps of 5–10%

These are not historical events — they are "what if" scenarios that
test the strategy's fragility.

### Framework Status

| Feature | Status |
|---|---|
| `app.run_monte_carlo_test()` — return-shuffle permutation | Implemented |
| `BacktestMonteCarloTest` with per-metric p-values | Implemented |
| `MonteCarloTest` stored in bundle per study | Implemented |
| White's Reality Check / Hansen's SPA (familywise) | **Not implemented** — study-level, uses existing MC infrastructure |
| Regime labels on `BacktestRun` for conditional evaluation | **Not implemented** — framework gap |
| Stress testing (synthetic scenarios) | Not implemented — study-level |

---

## 9. Phase 8 — Portfolio Construction

### Requirements

Moving from "does this strategy work?" to "how should I deploy
capital across multiple strategies?" This is the bridge between
research and production.

| Requirement | Rationale |
|---|---|
| Strategy correlation analysis | Two strategies with a 0.95 return correlation offer no diversification benefit |
| Risk budgeting | Allocate capital proportional to each strategy's risk-adjusted contribution |
| Drawdown-aware sizing | Reduce exposure after drawdowns, increase after recovery |
| Regime-conditional allocation | Shift capital toward strategies that outperform in the current regime |

### Framework Status

This phase is outside the current framework scope. The framework
produces the per-strategy evidence; portfolio construction is a
separate concern typically handled by a portfolio management layer.

---

## 10. Phase 9 — Production Readiness

### Requirements

| Requirement | Rationale |
|---|---|
| Live vs. backtest drift monitoring | The moment live performance diverges from backtest expectations, something has changed |
| Automatic kill switch | If live drawdown exceeds max backtest drawdown by a margin, halt trading |
| Execution quality monitoring | Compare actual fills vs. simulated fills to calibrate the slippage model |
| Regime detection | Know when the current market regime differs from those the strategy was validated on |
| Position reconciliation | Verify that the live portfolio matches the strategy's intended state |

### Framework Status

The framework supports live trading via the same `TradingStrategy`
class used in backtests. Production monitoring and kill switches are
outside the current scope.

---

## 11. Anti-Patterns

### Things that invalidate a backtest

| Anti-Pattern | Why it's wrong |
|---|---|
| **Single train/test split** | One split can be lucky. Walk-forward with multiple windows is the minimum |
| **No gap between train and test** | Adjacent windows leak information through indicator lookback periods |
| **Optimising on the test set** | If you ever use OOS results to adjust parameters, it becomes in-sample |
| **Reporting best-of-N without adjustment** | The expected max Sharpe of N random walks is √(2·ln(N)), not zero |
| **Ignoring execution costs** | A strategy with 0.2% edge per trade and 0.15% round-trip cost has a 0.05% edge, not 0.2% |
| **Survivorship bias in the universe** | Only testing on assets that exist today inflates returns by ~1-2% annually |
| **Using close prices for same-bar fills** | You cannot trade at the close — you observe the close, then trade at the next open |
| **Position sizing on future information** | Sizing based on the end-of-window portfolio value, not the current state |
| **Cherry-picking time periods** | Testing only on bull markets and calling it "backtested" |

### Things that look rigorous but aren't

| Practice | Why it's insufficient |
|---|---|
| **High Sharpe on a single long backtest** | A single Sharpe ratio is a point estimate with wide confidence intervals. Without knowing the number of trials, it's meaningless |
| **Walk-forward without pruning** | Running all combinations across all windows and selecting the best at the end is still overfitting — just slower |
| **Monte Carlo on a single strategy** | Tests whether *this* strategy is significant, but doesn't account for the fact that you *selected* it from N candidates |
| **OOS on a subset of the IS assets** | Not truly out-of-sample — the assets were part of the training universe |

---

## 12. References

1. Bailey, D.H. & López de Prado, M. (2014). "The Deflated Sharpe
   Ratio: Correcting for Selection Bias, Backtest Overfitting, and
   Non-Normality." *Journal of Portfolio Management*, 40(5), 94–107.

2. Bailey, D.H., Borwein, J., López de Prado, M. & Zhu, Q.J.
   (2017). "The Probability of Backtest Overfitting." *Journal of
   Computational Finance*, 20(4), 39–69.

3. White, H. (2000). "A Reality Check for Data Snooping."
   *Econometrica*, 68(5), 1097–1126.

4. Hansen, P.R. (2005). "A Test for Superior Predictive Ability."
   *Journal of Business & Economic Statistics*, 23(4), 365–380.

5. López de Prado, M. (2018). *Advances in Financial Machine
   Learning*. Wiley.

6. Almgren, R. & Chriss, N. (2001). "Optimal Execution of
   Portfolio Transactions." *Journal of Risk*, 3(2), 5–39.

7. Harvey, C.R. & Liu, Y. (2015). "Backtesting." *Journal of
   Portfolio Management*, 42(1), 13–28.

8. Harvey, C.R., Liu, Y. & Zhu, H. (2016). "...and the
   Cross-Section of Expected Returns." *Review of Financial
   Studies*, 29(1), 5–68.
