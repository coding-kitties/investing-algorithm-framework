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
- Validation of `warmup_window` against `pipeline.required_window()`
  so you get a clear error at startup if any data source is too short.
- First-class handling of partial bars (so you don't accidentally trade
  on an unclosed candle).
- Live observability hooks for pipeline output (print/log/snapshot).

## What stays the same

The same `Pipeline` subclasses you use in backtests run live.

## Want to help?

Track or comment on the implementation issue:
[#503 — Pipeline API: Phase 3 (live hardening)](https://github.com/coding-kitties/investing-algorithm-framework/issues/503).

## See also

- [Pipelines](pipelines.md) — concept page.
- [Pipelines: Event-driven backtest](pipelines-event-backtest.md) — full Phase 1 reference.
