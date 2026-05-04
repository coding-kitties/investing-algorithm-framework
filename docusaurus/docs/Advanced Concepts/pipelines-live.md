---
sidebar_position: 12
title: Pipelines — Live trading (roadmap)
description: Pipelines in live and paper trading. Tracked under #503.
---

# Pipelines: Live trading

:::info Status: hardening (Phase 3)

Because pipelines run inside the same event loop as backtests, they
**already execute** when you run a strategy live or in paper mode.
However, Phase 3 covers the production-grade work needed to declare
this officially supported: streaming-friendly panel updates, tighter
warmup-window guarantees, and explicit market-hours / partial-bar
handling.

Tracked under
[#503](https://github.com/coding-kitties/investing-algorithm-framework/issues/503).
:::

## What works today

Strategies with `pipelines = [...]` run end-to-end against any
configured live market. The pipeline output appears in
`data["YourPipelineClassName"]` exactly like in a backtest.

If you want to experiment, the same example covers both:
[`examples/pipeline_momentum_screener.py`](https://github.com/coding-kitties/investing-algorithm-framework/blob/dev/examples/pipeline_momentum_screener.py).

## What's planned for Phase 3

- A streaming panel that appends new bars instead of rebuilding from
  scratch.
- ✅ Validation of `warmup_window` against `pipeline.required_window()`
  so you get a clear error at startup if any data source is too short.
- ✅ Live envelope validation (≤ 50 symbols, daily-or-coarser
  timeframes) at first iteration in non-backtest environments.
- ✅ Universe-refresh cadence (`Pipeline.refresh_universe_every`) so
  the universe filter doesn't have to run every bar.
- ✅ Per-pipeline error resilience — a single failing pipeline is
  logged and skipped in live mode instead of killing the iteration.
- 🚧 Batched / async OHLCV fetch in `CCXTOHLCVDataProvider` (tracked
  for a follow-up PR — needs live integration testing).
- First-class handling of partial bars (so you don't accidentally trade
  on an unclosed candle).
- Live observability hooks for pipeline output (print/log/snapshot).

## Live envelope (shipped)

v1 of the live pipeline engine is intentionally conservative:

| Constraint | Value |
| --- | --- |
| Maximum unique OHLCV symbols per strategy | `50` |
| Minimum supported timeframe | daily (`24h`) |

These limits are checked once per run at the first iteration when the
environment is not `BACKTEST`. Violations raise
`OperationalException` with an actionable message naming the
strategy and the offending symbols / timeframe. Backtests are
unaffected — sub-daily timeframes and large universes keep working in
backtest mode exactly as before.

## Universe refresh cadence (shipped)

A pipeline can declare how often the universe filter should be
re-evaluated by setting the class attribute
`refresh_universe_every: timedelta`. Inside that cadence the engine
keeps the surviving symbol set fixed and skips evaluating the
universe filter, which is typically the most expensive part of the
pipeline.

```python
from datetime import timedelta

class DailyMomentum(Pipeline):
    sma200 = SMA(window=200)
    dollar_volume = AverageDollarVolume(window=30)

    universe = dollar_volume.top(50)
    signal = sma200.zscore(mask=universe)

    # Re-pick the top-50 universe once per day; reuse the
    # selection on every intra-day bar.
    refresh_universe_every = timedelta(days=1)
```

When `refresh_universe_every` is `None` (the default) the universe is
re-evaluated every bar, preserving Phase 1 / Phase 2 behaviour
exactly.

## Per-pipeline resilience (shipped)

In non-backtest environments a single pipeline raising during
`evaluate` is logged and the iteration continues with an empty output
frame for that pipeline — so an unrelated strategy on the same event
loop is not knocked out by one bad data source. Backtests still
re-raise so failures stay deterministic.

## Warmup validation (shipped)

When a strategy declares `pipelines = [...]`, the framework validates
at construction time that every OHLCV data source has a
`warmup_window` ≥ the pipeline's longest factor window. If any source
is short — or `warmup_window` is left unset — strategy instantiation
raises `OperationalException` with an actionable message listing the
offending sources and the required window size.

```python
class MomentumScreener(Pipeline):
    sma = SMA(window=200)


class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    pipelines = [MomentumScreener]
    data_sources = [
        DataSource(
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame=TimeFrame.ONE_HOUR,
            market="BITVAVO",
            warmup_window=200,   # must be >= 200 to satisfy SMA(200)
        ),
    ]
```

This eliminates a common failure mode in live deployments: a bot
silently trading on NaN factor columns until enough bars accrue.

## What stays the same

The same `Pipeline` subclasses you use in backtests run live.

## Stateless / serverless deployment (AWS Lambda, Azure Functions)

Live trading is frequently deployed on **AWS Lambda** or **Azure
Functions** via the framework's stateless mode (see
`investing_algorithm_framework/cli/deploy_to_aws_lambda.py` and
`deploy_to_azure_function.py`). The pipeline runtime is designed to
be safe in those environments:

- **No cross-invocation state.** Pipelines hold no module-level
  mutable state. Each call to `PipelineEngine.evaluate(...)` (event
  mode) and `VectorPipelineEngine.evaluate_window(...)` (vector mode)
  builds a fresh panel and a fresh result frame.
- **Per-evaluation cache, scoped via `contextvars`.** The shared
  sub-expression cache used by composite factors (e.g. `r + r.zscore()`
  reusing `r`'s computation) lives in a `ContextVar` that is
  installed at the start of each `evaluate` call and reset in a
  `finally` block. A warm Lambda / Functions container reusing the
  process between invocations sees a clean cache every time.
- **Pure factor composition.** `Factor.zscore()`, `demean()`,
  `winsorize()`, and arithmetic (`+ - * /`, unary `-`) all return new
  factor objects without mutating their inputs. Building a pipeline
  is a pure operation, so it's safe to construct pipelines at module
  load time on Lambda/Functions cold start.

## Want to help?

Track or comment on the implementation issue:
[#503 — Pipeline API: Phase 3 (live hardening)](https://github.com/coding-kitties/investing-algorithm-framework/issues/503).

## See also

- [Pipelines](pipelines.md) — concept page.
- [Pipelines: Event-driven backtest](pipelines-event-backtest.md) — full Phase 1 reference.
