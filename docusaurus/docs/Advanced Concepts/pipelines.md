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

## Phased rollout

Pipelines run today in the **event-driven backtest** path and in
**live** trading by way of the same event loop. Vector-mode pipelines
and cached/lazy execution are tracked separately.

| Mode | Status | Page |
| --- | --- | --- |
| Event-driven backtest | ✅ Phase 1 | [Pipelines: Event-driven backtest](pipelines-event-backtest.md) |
| Vector backtest | 🚧 Phase 2 ([#502](https://github.com/coding-kitties/investing-algorithm-framework/issues/502)) | [Pipelines: Vector backtest](pipelines-vector-backtest.md) |
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
