---
sidebar_position: 11
title: Pipelines — Vector backtest
description: Vector-mode pipeline execution. Phase 2 (#502) — shipped.
---

# Pipelines: Vector backtest

:::tip Status: shipped (Phase 2)
Vector-mode pipelines run by default whenever you backtest with
`BacktestService` — no opt-in needed. The vector engine evaluates each
declared factor across the **entire** backtest window once per
strategy iteration, with shared sub-expression caching.
:::

## How it works

When `BacktestService` runs, it inspects each strategy's `pipelines`
list and routes them through `VectorPipelineEngine`. For every
iteration:

1. The engine builds a long-form Polars panel
   `(datetime, symbol, open, high, low, close, volume)` truncated at
   the current bar (no look-ahead).
2. Each declared `Factor` is evaluated **once** in vectorised Polars,
   per symbol, over the full window.
3. A per-evaluation cache (a `ContextVar`) memoises shared
   sub-expressions — for example `r.zscore() - r.demean()` only
   computes `r` once.
4. The optional `universe` mask filters the result; the universe
   column itself is dropped from the output.
5. The strategy receives the wide frame via
   `data["YourPipelineClassName"]`.

The strategy author surface is unchanged from
[Pipelines: Event-driven backtest](pipelines-event-backtest.md): you
write the same `Pipeline` subclasses and read the same
`data["..."]` frames.

## Lazy / streaming execution

For memory-bound runs over very large universes you can opt the
post-factor pipeline (universe filter + drop + sort) onto Polars'
streaming engine:

```python
from investing_algorithm_framework.services.pipeline import (
    VectorPipelineEngine,
)

engine = VectorPipelineEngine(lazy=True)
result = engine.evaluate_window(
    pipeline_cls=MomentumScreener,
    data_object=panel_data,
    symbol_to_identifier=sym_id,
)
```

`lazy=True` is **bit-for-bit equivalent** to the default eager mode
(this is verified by an equivalence test in the suite). It only
changes how the result frame is collected — factors themselves still
return eager `pl.Series` values per symbol. On older Polars versions
that don't accept `engine="streaming"` on `collect`, the engine falls
back to a default collect transparently.

You typically don't need to instantiate `VectorPipelineEngine`
yourself; `BacktestService` handles it. The `lazy` flag is exposed for
direct users of the engine and for performance experiments.

## Equivalence with event mode

Vector and event mode are required to produce **identical** factor
values for the same panel and same `as_of`. The test suite enforces
this with cross-mode equivalence tests in
`tests/services/pipeline/test_vector_pipeline_engine.py`. If you find
a discrepancy, that's a bug — please file an issue.

## See also

- [Pipelines](pipelines.md) — concept page (factor algebra, transforms).
- [Pipelines: Event-driven backtest](pipelines-event-backtest.md) —
  same surface, event executor.
- [Pipelines: Live trading](pipelines-live.md) — stateless / serverless
  notes.
