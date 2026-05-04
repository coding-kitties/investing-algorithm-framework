---
sidebar_position: 9
title: Pipelines
description: Cross-sectional factor computation across many symbols, in one shot, on every iteration.
---

# Pipelines

A **Pipeline** lets your strategy compute factors across many symbols
at once, every iteration, and receive a tidy table of one row per
surviving symbol and one column per factor — instead of looping over
symbols and rebuilding indicators by hand.

If you have ever written a strategy that:

- ranks symbols by momentum / volatility / liquidity, then trades the
  top-`N`,
- restricts trading to a "tradeable universe" (e.g. top-100 by dollar
  volume),
- needs the **same** indicator set for every symbol,

…the pipeline API is the supported way to do it.

## What you get

```python
from investing_algorithm_framework import (
    AverageDollarVolume,
    Pipeline,
    Returns,
    TradingStrategy,
)

class MomentumScreener(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)

    universe = dollar_volume.top(100)        # tradeable universe
    alpha = momentum.rank(mask=universe)     # rank within universe


class MyStrategy(TradingStrategy):
    pipelines = [MomentumScreener]

    def run_strategy(self, context, data):
        screen = data["MomentumScreener"]    # Polars DataFrame
        top = screen.sort("alpha", descending=True).head(10)
        ...
```

The framework:

1. Collects each strategy's OHLCV data sources.
2. Builds a long-form panel `(datetime, symbol, open, high, low, close,
   volume)` truncated at the current bar (no look-ahead).
3. Computes each declared `Factor` per symbol in vectorised Polars.
4. Applies the optional `universe` filter as a top-level mask.
5. Hands you a wide DataFrame with one row per surviving symbol via
   `data["YourPipelineClassName"]`.

## Core concepts

### `Factor`

A per-symbol time-series computation. Phase 1 ships these built-ins:

| Factor | Inputs | Description |
| --- | --- | --- |
| `Returns(window)` | close | `close[t] / close[t - window] - 1` |
| `AverageDollarVolume(window)` | close, volume | rolling mean of `close * volume` |
| `SMA(window)` | close | simple moving average |
| `RSI(window)` | close | Wilder's RSI |
| `Volatility(window, periods_per_year=252)` | close | annualised stdev of log returns |
| `StaticPerSymbol(mapping, default=None)` | — | broadcasts a `dict[symbol, value]` (e.g. sector / market-cap) into the cross-section |
| `CrossSectionalMean(base, mask=None)` | base factor | per-bar equal-weight mean across surviving symbols |
| `RollingBeta(target, market, window>=2)` | two factors | rolling-window OLS beta `cov(t,m)/var(m)`; null when `var(m) == 0` |
| `Neutralize(target, exposures=[...], mask=None, add_intercept=True)` | factors | per-bar OLS residualisation of `target` against `exposures`; null on rank-deficient bars |

You can also subclass `CustomFactor` to compute your own.

### `Filter`

A boolean per-bar mask. `factor.top(n)` and `factor.bottom(n)` return
filters. Assigning a filter to the class attribute `universe` makes it
the pipeline's master mask: every other column is restricted to symbols
where the universe is `True`, and the universe column itself is
**dropped from the output**.

### Cross-sectional ops

```python
factor.rank(mask=universe)   # ascending ordinal rank within each bar
factor.top(n)                # boolean mask: top-n by descending value
factor.bottom(n)             # boolean mask: bottom-n by ascending value
```

### Cross-sectional transforms

Per-bar normalisation operators (Phase 2). Each takes an optional
`mask` so the statistic is computed only over the universe that
passes the mask:

```python
factor.zscore(mask=universe)             # (x - mean) / std per bar
factor.demean(mask=universe)             # x - mean per bar
factor.winsorize(0.01, 0.99,             # clip to per-bar quantiles
                 mask=universe)

# Group-relative variants — stats computed within each group
# (typically sector). `groups` accepts a dict[symbol, key] or any
# Factor that emits a per-symbol category.
factor.zscore(groups=SECTORS)            # z-score within sector
factor.demean(groups=SECTORS, mask=universe)
```

Where the cross-sectional `std` is `0` or undefined (e.g. only one
symbol survives the mask), `zscore` returns `null` rather than
`inf`/`NaN`. Masked-out symbols are excluded from the bar's
statistic *and* from the bar's output.

### Risk neutrality

When you want a factor's signal to be independent of structural
exposures (sector, beta to the market, multi-factor risk model),
use the built-in risk-neutrality primitives. They cover three
common cases:

**Sector neutrality** — z-score or demean *within* each sector
instead of across the whole universe by passing `groups=`. The
mapping can be a `dict[symbol, sector]` or any `Factor` that
emits a per-symbol category:

```python
SECTORS = {"AAPL": "Tech", "MSFT": "Tech", "JPM": "Fin", ...}

class SectorNeutralMomentum(Pipeline):
    momentum = Returns(window=60)
    signal = momentum.zscore(groups=SECTORS)   # z-score within sector
```

**Beta neutralisation** — strip a factor's exposure to the market
(or any other reference series) using `RollingBeta` and
`Neutralize`:

```python
from investing_algorithm_framework import (
    Returns, RollingBeta, CrossSectionalMean, Neutralize,
)

class BetaNeutralAlpha(Pipeline):
    r = Returns(window=1)
    market = CrossSectionalMean(r)               # equal-weight market
    beta = RollingBeta(r, market, window=60)
    alpha = Neutralize(r, exposures=[beta])      # market-neutral residual
```

**Multi-factor risk model** — pass several exposures to
`Neutralize` and the residual is orthogonal to all of them at
each bar (per-bar OLS):

```python
class FactorNeutralAlpha(Pipeline):
    r = Returns(window=1)
    size = StaticPerSymbol(MARKET_CAPS)          # cross-sectional size
    val = BookToPrice()
    mom = Returns(window=252)
    residual = Neutralize(r, exposures=[size, val, mom])
```

Bars where the system is rank-deficient (more exposures than
surviving symbols) yield `null` residuals so they're skipped
downstream rather than producing `NaN`.

### Factor algebra

Factors compose via the standard arithmetic operators. The framework
auto-coerces scalar operands and shares sub-expression results via a
per-evaluation cache, so the same input factor is computed once even
when it appears multiple times:

```python
class MyScreener(Pipeline):
    momentum = Returns(window=30)
    vol = Volatility(window=30)

    universe = AverageDollarVolume(window=30).top(100)

    # Composite alphas — `momentum` is computed once even though it
    # appears in two terms.
    risk_adjusted = momentum / vol
    score = (
        momentum.zscore(mask=universe)
        - 0.5 * vol.zscore(mask=universe)
    )
```

Supported operators: `+`, `-`, `*`, `/`, unary `-`. Both operands may
be `Factor` instances; either may be a Python `int` or `float`.
Division by zero leaves `inf` in place (downstream filters can drop
it) — for safe normalisation prefer `zscore`, which guards against
zero dispersion.

## Phased rollout

Pipelines run today in the **event-driven backtest** path and in
**live** trading by way of the same event loop. Vector-mode pipelines
and cached/lazy execution are tracked separately.

| Mode | Status | Page |
| --- | --- | --- |
| Event-driven backtest | ✅ Phase 1 | [Pipelines: Event-driven backtest](pipelines-event-backtest.md) |
| Vector backtest | ✅ Phase 2 ([#502](https://github.com/coding-kitties/investing-algorithm-framework/issues/502)) | [Pipelines: Vector backtest](pipelines-vector-backtest.md) |
| Live trading | 🚧 Phase 3 ([#503](https://github.com/coding-kitties/investing-algorithm-framework/issues/503)) | [Pipelines: Live trading](pipelines-live.md) |

Start with the event-driven backtest page — it covers the full Phase 1
surface area you can use today.

## Why opt-in?

Strategies that don't set `pipelines` pay **zero** cost: the engine is
not constructed, no panel is built, and the existing per-symbol data
flow is unchanged. You can adopt pipelines on a single strategy without
touching the rest of your codebase.

## See also

- [Pipelines: Event-driven backtest](pipelines-event-backtest.md) — full Phase 1 reference.
- Design doc: [`docs/design/pipeline-api.md`](https://github.com/coding-kitties/investing-algorithm-framework/blob/dev/docs/design/pipeline-api.md).
- Tracking issues: [#501 (Phase 1)](https://github.com/coding-kitties/investing-algorithm-framework/issues/501),
  [#502 (Phase 2)](https://github.com/coding-kitties/investing-algorithm-framework/issues/502),
  [#503 (Phase 3)](https://github.com/coding-kitties/investing-algorithm-framework/issues/503).
