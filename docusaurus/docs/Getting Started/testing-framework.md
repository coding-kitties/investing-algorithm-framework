---
sidebar_label: Strategy Testing Framework
---

# Scenario-Based Strategy Testing

`StrategyScenario` provides **a first-class, scenario-based strategy regression
framework for quantitative trading**. Arrange an initial portfolio, inspect a
decision, or replay generated market conditions through the strategy's production
order and fill pipeline.

Use scenarios to reproduce specific bugs and assert invariants such as "a crash
triggers protection without new long entries." Use a
[backtest](./backtesting.md) to evaluate performance over a wider dataset.
Passing scenario tests does not demonstrate profitability.

:::note Availability
These APIs are available in **v9.1.0 and later**. Upgrade to that release or use
a source checkout containing `StrategyScenario`; version 9.0.0 does not include
this guide's scenario APIs.
:::

## Quick start: seed an existing trade

Both public import paths are supported:
`from investing_algorithm_framework import StrategyScenario` and
`from investing_algorithm_framework.testing import StrategyScenario`.

This minimal test needs no credentials, exchange connection, or market data:

```python
from datetime import datetime, timedelta, timezone
import unittest

from investing_algorithm_framework import (
    DataSource, PositionSize, Schedule, StrategyScenario,
    TimeUnit, TradingStrategy,
)

START = datetime(2025, 1, 15, tzinfo=timezone.utc)
BAR = timedelta(hours=2)


class ReferenceStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            identifier="btc_2h", symbol="BTC/EUR", market="BITVAVO",
            data_type="OHLCV", time_frame="2h", pandas=True,
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25),
    ]

    def generate_signals(self, context, data):
        return []


class TestExistingTrade(unittest.TestCase):
    def test_seeded_trade(self):
        with StrategyScenario(
            ReferenceStrategy(),
            initial_cash=1_000,
            trading_symbol="EUR",
            start=START,
        ) as scenario:
            trade = scenario.open_trade(
                "BTC", amount=2, price=100, fee=1,
                opened_at=START - BAR,
            )
            self.assertEqual(trade.open_price, 100)
            self.assertEqual(scenario.context.get_unallocated(), 799)
            self.assertEqual(scenario.context.get_position("BTC").cost, 200)
            scenario.check_consistency()
```

Save the test in an importable test module and run it with `python -m unittest`.
The context manager releases the scenario's resources, including when the test
body raises. Each scenario owns a separate in-memory store, service container,
clock, and strategy runtime state; it does not write into user resource or
backtest directories.

Always construct a fresh strategy for each independently evaluated scenario.
A strategy cannot belong to two open scenarios or initialize a new scenario
after it has already evaluated bars.

## Constructor options and units

| Parameter | Meaning |
| --- | --- |
| `strategy` | A strategy instance, not its class. |
| `initial_cash` | Finite, nonnegative quote-currency cash. |
| `start` / `start_date` | Initial aware datetime on a UTC hour. Supply at least one; if both are supplied, they must identify the same instant. |
| `end_date` | Optional inclusive stepping limit at or after the start. Omitted or `None` means unbounded. |
| `trading_symbol` | Quote currency, such as `"EUR"`. |
| `market` | Market name; inferred when declared data sources name exactly one market. |
| `position_mode` | `PositionMode.NETTING` by default, or `PositionMode.HEDGE`. |
| `portfolio_configuration` | A `PortfolioConfiguration` instead of the separate currency/market/mode arguments. Conflicting initial balances are rejected. |
| `data_generator` | Optional datetime-based whole-strategy callback for stepping. |

For example, to retain independent long and short legs:

```python
from investing_algorithm_framework import PortfolioConfiguration, PositionMode

configuration = PortfolioConfiguration(
    market="BITVAVO", trading_symbol="EUR",
    position_mode=PositionMode.HEDGE,
)
with StrategyScenario(
    ReferenceStrategy(), initial_cash=1_000, start_date=START,
    end_date=None, portfolio_configuration=configuration,
) as scenario:
    scenario.open_trade("BTC", amount=1, price=100)
    scenario.open_trade("BTC", amount=1, price=100, direction="short")
    scenario.check_consistency()
```

Prices, fees, cash allocations, and `quote_amount` use the quote currency.
`amount` and `sell_amount` use asset units. A fee is separate from the entry
price and position cost basis.

## Arrange positions, orders, protection, and history

Seeding calls use production order/trade services. They keep trades, cash,
positions, cost basis, allocations, and reservations consistent; changing only
a position amount would not create a valid fixture.

| Helper | Purpose and important parameters |
| --- | --- |
| `open_trade(symbol, amount=..., price=...)` | Seed a filled lot and return its `Trade`. Supports `direction="long"` / `"short"`, `fee`, `opened_at`, and `apply_strategy_rules`. |
| `register_position(...)` | Same lot-seeding parameters, but return its aggregate `Position`. Repeated calls add lots rather than replace holdings. |
| `place_order(symbol, side=..., amount=..., price=...)` | Seed a pending limit order. Supports BUY, SELL, SHORT, COVER, `created_at`, and `apply_strategy_rules`. Returns an `Order`. |
| `add_stop_loss(trade, percentage=...)` | Attach protection to an open lot; supports `trailing`, `sell_percentage`, and `created_at`. |
| `add_take_profit(trade, percentage=...)` | Attach a profit rule with the same optional parameters. |
| `mark_price(symbol, price, at=...)` | Seed a historical mark and trailing-rule state for the symbol's open lots. |
| `record_cooldown(symbol, side=..., bars_ago=...)` | Seed previous order-emission history without advancing time. |
| `check_consistency()` | Verify accounting invariants; not a performance or signal-quality assertion. |

Entries attach configured strategy risk rules by default. Set
`apply_strategy_rules=False` if you intend to attach custom fixture rules.
Seeded order IDs are generated automatically; registration does not link an
existing/custom order ID.

Pending entry/cover orders reserve cash; pending sells reserve long asset units.
Seeding deliberately arranges state without requiring an indicator signal or
applying the next decision's eligibility gates.

```python
from investing_algorithm_framework import CooldownRule, SignalSide

with StrategyScenario(
    ReferenceStrategy(cooldowns=[
        CooldownRule(symbol="BTC", trigger="buy", blocks="buy", bars=3),
    ]),
    initial_cash=1_000, trading_symbol="EUR", start=START,
) as scenario:
    trade = scenario.open_trade(
        "BTC", amount=2, price=100, opened_at=START - 3 * BAR,
        apply_strategy_rules=False,
    )
    scenario.add_stop_loss(
        trade, percentage=5, trailing=True, created_at=START - 3 * BAR,
    )
    scenario.add_take_profit(
        trade, percentage=20, created_at=START - 3 * BAR,
    )
    scenario.mark_price("BTC", 110, at=START - BAR)
    scenario.place_order("BTC", side="SELL", amount=0.5, price=115)
    scenario.record_cooldown(
        "BTC", side=SignalSide.OPEN_LONG, bars_ago=1,
    )
    assert scenario.context.get_unallocated() == 800
    assert scenario.context.get_open_trades()[0].available_amount == 1.5
    assert scenario.preview_cooldown("BTC").remaining_bars == 2
    assert scenario.now == START
    scenario.check_consistency()
```

Seed timestamps cannot be in the future relative to the scenario clock, and
marks must follow the relevant trade/rule history. A mark that already triggers
protection is rejected: use replayed steps to test actual protective execution.
Record cooldown events oldest first (`bars_ago` must not increase).

## Inspect decisions without execution

| Utility | What it returns |
| --- | --- |
| `get_position_size(symbol, price=..., prices=...)` | Raw strategy-requested quote allocation, before eligibility, cash, scaling, or exposure limits. Honors strategy sizing overrides. |
| `preview_order(symbol, price=..., side=..., prices=...)` | Sized intents and diagnostic traces after production eligibility/sizing/budget phases. `approved` is false when no intent qualifies. |
| `get_stop_loss_rule(symbol, side=...)` / `get_take_profit_rule(...)` | Effective configuration, or `None`. Risk lookup `side` means `"long"` / `"short"`. |
| `preview_stop_loss(symbol, price=..., amount=..., side=..., prices=...)` / `preview_take_profit(...)` | Detached production risk models, or `None`; inspect trigger prices and sell amounts without attaching stored rules. |
| `get_cooldown_rules(symbol)` | Applicable configured rules, whether currently active or not. |
| `preview_cooldown(symbol, side=...)` | Next-decision blocking rules and remaining bars without consuming history. Uses a `SignalSide`. |

Previews do not generate indicators/signals, submit/fill orders, or advance
the clock. `preview_order` evaluates one explicit intent, not simultaneous
multi-symbol allocation. A trailing take-profit preview initially has no
trigger price until it is armed by a favorable move.

Pass explicit quote-currency prices for other held/ordered assets when a
portfolio-aware preview needs to value them:

```python
with StrategyScenario(
    ReferenceStrategy(position_sizes=[
        PositionSize(symbol="BTC", fixed_amount=250),
    ]),
    initial_cash=1_000, trading_symbol="EUR", start=START,
) as scenario:
    scenario.place_order("ETH", side="BUY", amount=9, price=100)
    assert scenario.get_position_size(
        "BTC", price=100, prices={"ETH": 100},
    ) == 250
    preview = scenario.preview_order("BTC", price=100, prices={"ETH": 100})
    assert preview.approved
    assert preview.orders[0].quote_amount == 100
    assert preview.orders[0].amount == 1
    assert scenario.now == START
```

Here the raw request remains 250 EUR, but pending ETH reserves 900 EUR and
the preview is budgeted down to 100 EUR. Read `preview.traces` to distinguish
cash limits, cooldown blocking, and open-order conflicts.

Calling `strategy.generate_signals(scenario.context, data)` directly is another
useful isolated test. It produces raw signals only, without the downstream
eligibility/order pipeline. Use scheduled stepping for execution assertions.

## Query trades and orders

`register_position` returns a `Position`; `open_trade` returns a `Trade`.
Query by position when you need all its lots/orders, including both HEDGE legs:

```python
with StrategyScenario(
    ReferenceStrategy(), initial_cash=1_000, trading_symbol="EUR", start=START,
) as scenario:
    position = scenario.register_position("BTC", amount=2, price=100, fee=1)
    trades = scenario.get_trades(
        position=position, target_symbol="BTC", trading_symbol="EUR",
        market="BITVAVO", portfolio=position.portfolio_id,
        status="OPEN", opened_since=START,
    )
    orders = scenario.get_orders(
        position=position, target_symbol="BTC", status="CLOSED",
        order_type="LIMIT", order_side="BUY", market="BITVAVO",
    )
    assert len(trades) == len(orders) == 1
    assert trades[0].orders[0].id == orders[0].id
```

- Trade filters: `target_symbol`, `trading_symbol`, `market`, `portfolio`
  (object or ID), `status`, inclusive `opened_since`, and `position`.
- Order filters: `target_symbol`, `status`, `order_type`, `order_side`,
  `market`, and `position`.
- Status/type/side filters accept their framework enums or strings, matching
  `Context`. All supplied filters intersect; omitted filters are unrestricted.
- Omitting `status` retains open and historical rows. A filled opening Order
  can be CLOSED while the Trade it opened is still OPEN.
- Results preserve Context ordering and do not advance or mutate state.
  Fetch again after execution to inspect changes; models are snapshots.

## Generate data and advance scheduled bars

A whole-strategy callback receives each evaluation datetime and returns frames
keyed by **every declared data-source ID**. Include sufficient history for
indicators and all potential fills since the previous step. Do not mutate the
scenario from its callback.

OHLCV frames can be pandas or Polars, with canonical Open/High/Low/Close/Volume
columns and a datetime index/column. Source `pandas` configuration determines
the frame type passed to the strategy. Timestamps are candle opening times:
only completed candles are evaluated.

The following threshold strategy intentionally avoids indicator complexity
to demonstrate emission and later fills:

```python
import pandas as pd
from investing_algorithm_framework import Signal


class ReplayStrategy(ReferenceStrategy):
    def generate_signals(self, context, data):
        close = data["btc_2h"]["Close"].iloc[-1]
        held = context.get_open_trades(target_symbol="BTC")
        if not held and close <= 100:
            return [Signal("BTC", SignalSide.OPEN_LONG)]
        if held and close >= 120:
            return [Signal("BTC", SignalSide.CLOSE_LONG)]
        return []


def generate_data(at):
    frame = pd.DataFrame({
        "Open": [100, 100, 125],
        "High": [101, 126, 126],
        "Low": [99, 99, 124],
        "Close": [100, 125, 125],
        "Volume": [1_000.] * 3,
    }, index=pd.date_range(START, periods=3, freq="2h"))
    return {"btc_2h": frame.loc[frame.index + BAR <= at]}


with StrategyScenario(
    ReplayStrategy(), initial_cash=1_000, trading_symbol="EUR",
    start_date=START, end_date=START + 3 * BAR,
    data_generator=generate_data,
) as scenario:
    entry = scenario.step()
    assert entry.datetime == START + BAR
    assert entry.orders[0].status == "OPEN"
    assert entry.filled_orders == ()

    exit_step, final = scenario.advance_bars(2)
    assert exit_step.filled_orders[0].id == entry.orders[0].id
    assert final.filled_orders[0].id == exit_step.orders[0].id
    assert scenario.get_trades(status="OPEN") == []
    assert scenario.get_orders(status="OPEN") == []
    scenario.check_consistency()
```

`step()` advances strictly to the next scheduled time, evaluates existing
orders/protection, and then runs the strategy pipeline. `advance_bars(count)`
does the same for multiple decisions. It checks requested times against
`end_date` before executing any of them; exceeding the limit raises explicitly.
There is no forced liquidation at the final date.

### Per-symbol/source callbacks

Instead of a whole-strategy callback, register each OHLCV source separately:

```python
with StrategyScenario(
    ReferenceStrategy(), initial_cash=1_000, trading_symbol="EUR", start=START,
) as scenario:
    candles = [{
        "timestamp": START, "open": 100, "high": 101,
        "low": 99, "close": 100, "volume": 1_000,
    }]
    scenario.register_data_generator(
        "BTC",
        lambda at: (
            candle for candle in candles
            if candle["timestamp"] + BAR <= at
        ),
    )
    result = scenario.step()
    assert result.datetime == START + BAR
```

The callback receives the datetime and returns a frame or iterable of candle
records, not a bar-by-bar callback without arguments. A base symbol must resolve
to one declared OHLCV source; use its exact ID (`"btc_2h"`) when ambiguous.
Register every source and do not mix per-source and whole-strategy modes.
All held/ordered assets need declared execution OHLCV in the quote currency;
the finest declared timeframe for a pair supplies its execution candles.

### Step results and price gaps

`ScenarioStepResult` contains detached snapshots:

| Field | Meaning |
| --- | --- |
| `datetime` | Scheduled evaluation time. |
| `signals` | Raw strategy signals, not necessarily approved. |
| `orders` | Orders created this step, including protective exits. |
| `filled_orders` | Orders whose filled quantity increased this step, including partial fills. |
| `traces` | Production diagnostic traces. |

A newly emitted order cannot fill retroactively on its signal candle. It
normally fills on a later eligible candle, and unmatched limits can remain
pending. Protective orders follow production execution semantics too: a crash
can gap past a trailing-stop threshold, so that threshold is not a guaranteed
fill price.

## Validation, isolation, and failure handling

- Invalid fixtures raise actionable `ScenarioSetupError` messages rather than
  silently fixing cash, holdings, or history. NETTING rejects opposing lots;
  use HEDGE when simultaneous long/short holdings are intentional.
- `check_consistency` raises `ScenarioStateError` when ledger invariants fail.
- Generator/data-validation errors occur before evaluation changes state and
  can be corrected before retrying.
- A production evaluation failure may have partial effects; it is surfaced
  explicitly and further stepping is blocked. Create a fresh scenario rather
  than assuming rollback. Earlier successful steps are not rolled back.
- Use the context manager or call `close()` for cleanup. Closing is idempotent;
  using a closed scenario raises.
- Scenarios supply offline state/data, but your own callback, strategy, or
  custom hook must also avoid external I/O. Add a socket guard to tests when
  you want to enforce this contract.

## Full confluence and crash reference

The [runnable RSI/EMA showcase](https://github.com/coding-kitties/investing-algorithm-framework/blob/main/examples/testing_framework/example.py)
includes warmup generation, dynamic sizing overrides, cooldowns, reservations,
historical marks, bounded stepping, and an extreme crash with a trailing stop.
It uses the public API and Python `unittest`:

```bash
python -m unittest examples.testing_framework.example -v
```

See also [Strategies](./strategies.md),
[Position Modes](../Advanced%20Concepts/position-modes.md), and
[Risk Rules](../Risk%20Rules/overview.md).
