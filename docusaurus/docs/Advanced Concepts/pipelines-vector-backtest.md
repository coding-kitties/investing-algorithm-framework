---
sidebar_position: 11
title: Pipelines — Vector backtest (roadmap)
description: Vector-mode pipeline execution. Tracked under #502.
---

# Pipelines: Vector backtest

:::info Status: not yet shipped (Phase 2)

Vector-mode pipelines are tracked under
[#502](https://github.com/coding-kitties/investing-algorithm-framework/issues/502).
The public API (`Pipeline`, `Factor`, `Filter`) defined in
[Pipelines: Event-driven backtest](pipelines-event-backtest.md) is
intentionally engine-agnostic, so strategies you write against Phase 1
will keep working when Phase 2 lands.
:::

## What's planned

- A vector executor that materialises every factor in the pipeline
  once over the **entire** backtest window, instead of rebuilding the
  panel on each event.
- Integration with the existing vector backtester (see
  [Vector backtesting](vector-backtesting.md)).
- Cached intermediate frames so a `rank` of a `Returns` doesn't
  recompute returns.
- Optional Polars **lazy** execution path for memory-bound runs.

## What stays the same

The strategy author surface — declaring a `Pipeline` subclass, listing
it on `strategy.pipelines`, and reading
`data["YourPipelineClassName"]` inside `run_strategy` — does not
change. Switching from event mode to vector mode is meant to be a
runner choice, not a strategy rewrite.

## Want to help?

Track or comment on the implementation issue:
[#502 — Pipeline API: Phase 2 (vector executor)](https://github.com/coding-kitties/investing-algorithm-framework/issues/502).

## See also

- [Pipelines](pipelines.md) — concept page.
- [Pipelines: Event-driven backtest](pipelines-event-backtest.md) — what works today.
