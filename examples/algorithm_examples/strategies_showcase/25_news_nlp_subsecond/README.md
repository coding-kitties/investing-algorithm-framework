# 25 — News / NLP Event-driven Strategies

**Fit:** 🟡 Currently not directly implementable, but **planned** — see [#534](https://github.com/coding-kitties/investing-algorithm-framework/issues/534).

## Status today

Strategies that react to discrete events (macro releases, listing
announcements, on-chain alerts, sentiment spikes from a social-media feed)
are awkward to express today because every `TradingStrategy` is woken on a
fixed bar schedule (`time_unit` + `interval`). The *signal* is the arrival
of a message, not the close of a bar — and the framework currently has no
way for a strategy to say *"run me when X happens"*.

Concrete gaps:

1. **No trigger abstraction.** A strategy declares one heartbeat
   (`time_unit`/`interval`); it cannot also subscribe to *"fire me when an
   event of type X arrives"*.
2. **No event data provider family.** `DataProvider` is a *pull* interface
   (the engine asks for data each iteration). There is no base class for a
   provider that *pushes* discrete events into the runtime — neither
   polled (every N seconds against a REST/RSS endpoint) nor streamed
   (websocket / SSE).
3. **No event tape for backtests.** Even if events arrived live, the
   backtest engine has no way to replay a historical event tape merged
   with bar timestamps.

## Planned path forward — issue [#534](https://github.com/coding-kitties/investing-algorithm-framework/issues/534)

The proposal in #534 closes all three gaps with a small, additive change:

1. **`Trigger` abstraction** — `IntervalTrigger` (sugar for the existing
   `time_unit`/`interval`) plus `EventTrigger(source=..., filter=...)`.
   A strategy can declare any combination of triggers.
2. **`EventDataProvider` family** — `PolledNewsDataProvider` (HTTP poll
   every N seconds) and `WebSocketEventDataProvider` (subscribe to a
   stream).
3. **`EventBus` in the live runtime** + **historical event-tape replay**
   in the backtest engine.

When that lands, the example below becomes runnable and this folder moves
from 🟡 to 🟢.

## Sketch of the future strategy

```python
from investing_algorithm_framework import (
    TradingStrategy, EventTrigger, IntervalTrigger,
    PolledNewsDataProvider, TimeUnit,
)

class NewsReactionStrategy(TradingStrategy):
    triggers = [
        IntervalTrigger(time_unit=TimeUnit.MINUTE, interval=5),  # heartbeat
        EventTrigger(source="news", filter=lambda e: e.symbol == "BTC"),
    ]
    data_sources = [
        PolledNewsDataProvider(
            identifier="news",
            url="https://example.com/api/crypto-news",
            poll_interval_seconds=10,
        ),
        # ... usual OHLCV sources
    ]

    def run_strategy(self, context, data, event=None):
        if event is None:
            return  # heartbeat — nothing to do this minute
        if event.sentiment > 0.7:
            # bullish news on BTC — open a small position
            ...
```

## What you can do today

For *non-time-critical* sentiment overlays (e.g. *"increase risk if
average sentiment over the past day > X"*) you can already:

- Pre-compute a sentiment score offline.
- Ingest it via a custom `DataProvider` that returns it as a regular time
  series.
- Read it in a bar-driven `run_strategy`, exactly like the multi-factor
  pattern in [04_multi_factor_portfolio](../04_multi_factor_portfolio).

That works today; what #534 adds is **second-level reactivity** to fresh
events as they arrive.

## Out of scope

True sub-millisecond HFT remains out of scope for this framework — see
[23_hft](../23_hft) and [21_active_market_making](../21_active_market_making).
The trigger work in #534 is aimed at the *seconds-to-minutes* regime where
news-API latency lives, not the microsecond regime.
