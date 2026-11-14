---
sidebar_position: 10
title: Pipelines — Event-driven backtest
description: Use cross-sectional pipelines in the event-driven backtest engine (Phase 1, available today).
---

# Pipelines: Event-driven backtest

This is the full Phase 1 reference. Read [Pipelines](pipelines.md) first
for the high-level concept.

## Quick start

```python
from investing_algorithm_framework import (
    AverageDollarVolume,
    BacktestDateRange,
  BacktestWindow,
    Context,
    DataSource,
  DataType,
    Pipeline,
    Returns,
  Schedule,
  Study,
    TimeUnit,
    TradingStrategy,
  Universe,
    create_app,
)


class MomentumScreener(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=30)

    universe = dollar_volume.top(3)
    alpha = momentum.rank(mask=universe)


class CrossSectionalMomentum(TradingStrategy):
    algorithm_id = "cross-sectional-momentum"
  schedule = Schedule.every(1, TimeUnit.DAY)
    data_sources = [
        DataSource(
      data_type=DataType.OHLCV,
            market="binance",
            symbol=symbol,
            warmup_window=60,
            time_frame="1d",
            identifier=f"{symbol}-ohlcv",
        )
        for symbol in ["BTC/EUR", "ETH/EUR", "SOL/EUR", "ADA/EUR", "XRP/EUR"]
    ]
    pipelines = [MomentumScreener]

    def generate_signals(self, context: Context, data):
        screen = data["MomentumScreener"]
        top = screen.sort("alpha", descending=True).head(2)
        for row in top.iter_rows(named=True):
            print(row["symbol"], row["momentum"], row["alpha"])
      return ()


if __name__ == "__main__":
  app = create_app()
    app.run_backtest(
    strategy=CrossSectionalMomentum(),
    study=Study(
      name="cross-sectional-momentum",
      universe=Universe(market="binance", trading_symbol="EUR"),
      initial_capital=1_000,
      backtest_windows=[BacktestWindow(
        train_range=BacktestDateRange(
          start_date="2024-01-01",
          end_date="2024-06-01",
          name="research",
        ),
      )],
        ),
    )
```

See the complete
[cross-sectional pipeline tutorial](https://github.com/coding-kitties/investing-algorithm-framework/tree/dev/examples/advanced_tutorials/cross-sectional-pipelines).

## How it works

On every iteration of the event loop:

1. The framework discovers your strategy's OHLCV data sources from
   `strategy.data_sources` (filtered by `DataType.OHLCV`).
2. For each `Pipeline` listed in `strategy.pipelines`:
   - Each per-symbol OHLCV frame is converted to Polars (Pandas inputs
     are auto-converted) and lower-cased.
   - The frames are stacked into a long-form panel and **truncated at
     the current bar** (`datetime <= as_of`) — guaranteed no
     look-ahead.
   - Each declared `Factor` is computed in vectorised Polars over the
     full panel.
   - The pipeline's `universe` filter (if any) is applied as a top-level
     mask; symbols failing the mask are dropped.
   - The frame is sliced to the current bar, and the result is stored
     under `data["YourPipelineClassName"]`.

The output is a `polars.DataFrame` with columns:

```
symbol  | <factor_1> | <factor_2> | ... | <factor_n>
```

Symbols with no data at the current bar (e.g. listed late) are dropped.

## Declaring a pipeline

```python
from investing_algorithm_framework import (
    AverageDollarVolume, Pipeline, Returns, RSI, SMA, Volatility,
)

class MyScreen(Pipeline):
    # Any factor declared as a class attribute becomes an output column
    # named after the attribute.
    momentum = Returns(window=30)
    rsi = RSI(window=14)
    vol = Volatility(window=30)

    # Optional: a Filter assigned to `universe` becomes the master mask.
    # Every other column is restricted to symbols where universe is True.
    # The universe column itself is NOT exposed in the output.
    universe = AverageDollarVolume(window=30).top(100)

    # `rank` works inside the universe.
    alpha = momentum.rank(mask=universe)
```

Rules enforced at class definition time:

- A pipeline must declare at least one factor column (otherwise
  `TypeError`).
- The `universe` attribute, if present, **must** be a `Filter` (e.g.
  `factor.top(n)` / `factor.bottom(n)`); using a plain `Factor` raises
  `TypeError`.
- Factors and filters are inherited via the MRO; subclass declarations
  override parent ones with the same name.

## Built-in factors

| Class | Inputs | Notes |
| --- | --- | --- |
| `Returns(window)` | close | `close[t] / close[t - window] - 1` |
| `AverageDollarVolume(window)` | close, volume | rolling mean of `close * volume` |
| `SMA(window)` | close | simple moving average |
| `RSI(window)` | close | Wilder's RSI; clamps to 100 when there are no losses |
| `Volatility(window, periods_per_year=252)` | close | rolling stdev of log returns × √periods_per_year |

All built-ins compute per-symbol via `over("symbol")` so symbols are
independent.

## Custom factors

Subclass `CustomFactor` and implement `compute_panel`:

```python
import polars as pl
from investing_algorithm_framework import CustomFactor

class HighLowRange(CustomFactor):
    inputs = ["high", "low"]
    window = 1

    def compute_panel(self, panel: pl.DataFrame) -> pl.Series:
        return (panel["high"] - panel["low"]).rename("range")
```

`compute_panel` receives the full long-form panel and must return a
`pl.Series` aligned with the panel rows. Set:

- `inputs` — the OHLCV columns you read from the panel.
- `window` — the lookback in bars. Strategy construction validates it against
  each OHLCV source's `warmup_window`; it is also exposed through
  `pipeline.required_window()`.

## Cross-sectional ops

```python
factor.rank(mask=optional_filter)   # ascending ordinal rank per bar
factor.top(n)                       # mask: top-n per bar by descending value
factor.bottom(n)                    # mask: bottom-n per bar by ascending value
```

`rank` returns ordinal ranks (1, 2, 3, …) within each `datetime`. With
a `mask`, symbols outside the mask receive `null`.

## Reading the result

```python
def generate_signals(self, context, data):
    screen: pl.DataFrame = data["MomentumScreener"]
    if screen.is_empty():
    return ()  # universe drained or warmup not yet satisfied

    top = screen.sort("alpha", descending=True).head(5)
    symbols = top["symbol"].to_list()
  return ()
```

Common patterns:

```python
# Symbol → row dict
rows = {row["symbol"]: row for row in screen.iter_rows(named=True)}

# To pandas if you prefer:
pdf = screen.to_pandas()
```

## Performance notes

Event-mode evaluation is **eager**: the panel and factor values are rebuilt on
every iteration. That is suitable for daily/hourly backtests with up to a few
hundred symbols. For larger research runs, use the vector pipeline executor,
which materialises factors over the full backtest window.

## Limitations

- Factor results are not cached between bars in event mode.
- Only OHLCV inputs. External data joining is on the roadmap.

Factor arithmetic and cross-sectional transforms use the same declarative API
documented on the [Pipelines](pipelines.md) page.

## Troubleshooting

- **`TypeError: <Pipeline>.universe must be a Filter`** — assign a
  `Filter` (e.g. `factor.top(100)`), not a raw `Factor`.
- **`KeyError: ... missing required column 'volume'`** — your data
  source is not OHLCV; pipelines need full OHLCV frames.
- **Empty result frame** — either your warmup hasn't yet satisfied the
  largest `window`, or your universe filtered every symbol out.

## See also

- [Pipelines](pipelines.md) — concept page.
- [Pipelines: Vector backtest](pipelines-vector-backtest.md) — whole-window execution.
- [Pipelines: Live trading](pipelines-live.md) — supported envelope and hardening status.
- Design doc: [`docs/architecture/strategy/pipeline-api.md`](https://github.com/coding-kitties/investing-algorithm-framework/blob/dev/docs/architecture/strategy/pipeline-api.md).
