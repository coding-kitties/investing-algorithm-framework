# Pipeline API — Design Doc

> Status: **DRAFT for review**.
> Tracking issue: [#438](https://github.com/coding-kitties/investing-algorithm-framework/issues/438).
> Phase issues: [#501](https://github.com/coding-kitties/investing-algorithm-framework/issues/501) (event), [#502](https://github.com/coding-kitties/investing-algorithm-framework/issues/502) (vector), [#503](https://github.com/coding-kitties/investing-algorithm-framework/issues/503) (live).

## 1. Goals & non-goals

### Goals

1. Declarative cross-sectional factor / filter / classifier computation across an asset universe at each bar.
2. Look-ahead-safe by construction: a factor evaluated at bar `t` sees only data with timestamp `≤ t`.
3. Strict opt-in: strategies without `pipelines = [...]` see **zero** behavioural or performance change.
4. Three execution backends (event backtest, vector backtest, live) sharing the same `Pipeline` definition.

### Non-goals (v1)

- Full Zipline-Pipeline parity (no classifier hierarchies, no winsorization, no OLS factors).
- Live pipelines on sub-daily timeframes.
- Universes outside the supported envelope (see §6).
- Cross-market order routing (separate issue).

## 2. Public API

```python
from investing_algorithm_framework import (
    TradingStrategy, Pipeline, Returns, AverageDollarVolume, TimeUnit,
)

class MomentumScreener(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum = Returns(window=60)

    universe = dollar_volume.top(100)
    alpha = momentum.rank(mask=universe)


class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    pipelines = [MomentumScreener]
    universe = ["BTC/EUR", "ETH/EUR", ...]   # candidate symbols

    def run_strategy(self, context, data):
        out = data["MomentumScreener"]   # pl.DataFrame, one row per surviving symbol
        ...
```

### Class attributes added to `TradingStrategy`

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `pipelines` | `list[type[Pipeline]]` | `[]` | Pipelines to run before each `run_strategy` call. |
| `universe` | `list[str] \| list[DataSource]` | `[]` | Candidate symbols. Folded into `data_sources` at app startup; pipelines filter down. |

### `Pipeline` class

- Class attributes that are `Factor` / `Filter` instances are introspected via `__init_subclass__`.
- A class attribute named `universe` is treated as the **root mask**: if present, every other column is computed on the masked subset.
- All other attributes become columns of the output frame.

## 3. Panel shape

The engine's internal representation is a **long-form Polars DataFrame**:

```
schema = {
    "datetime": pl.Datetime,
    "symbol":   pl.Utf8,
    "open":     pl.Float32,
    "high":     pl.Float32,
    "low":      pl.Float32,
    "close":    pl.Float32,
    "volume":   pl.Float32,
}
```

Long-form is chosen because:

- Polars rolling/group-by is faster on long form than on wide.
- Sparse symbols (delisted, late-listed) are natural — no NaN columns.
- Cache files are smaller (no per-symbol column duplication).

Per-bar pipeline output handed to the strategy is a **wide** frame keyed by symbol:

```
out = pl.DataFrame({
    "symbol":        pl.Utf8,
    "<factor name>": pl.Float64,    # one column per Factor/Filter on the Pipeline
    ...
})
```

## 4. Engine API (internal)

```python
class PipelineEngine(Protocol):
    def evaluate_at(
        self,
        pipeline: type[Pipeline],
        as_of: datetime,
    ) -> pl.DataFrame: ...
    """Event mode: return wide per-symbol frame for the given timestamp."""

    def evaluate_range(
        self,
        pipeline: type[Pipeline],
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame: ...
    """Vector mode: return long (date, symbol)-indexed frame for the range."""
```

Two implementations:

- `LazyPolarsPipelineEngine` (event + vector). Compiles Factor expressions into a single `pl.LazyFrame` plan; `collect()` only at the boundary.
- `LiveBatchedPipelineEngine` (Phase 3). Adds async batched fetch + universe-refresh.

## 5. Cache key (Phase 2)

Cache lives under `<resource_dir>/pipeline_cache/`. Key:

```
hash(
    universe_hash:   sha1(sorted(symbol_list)),
    daterange:       (start.isoformat(), end.isoformat()),
    timeframe:       e.g. "1d",
    expr_hash:       sha1(canonical_repr(factor_expression_tree)),
    schema_version:  int,           # bump on any cache-incompatible change
)
```

Hits return the cached panel/factor frame without recomputation.
Parameter sweeps over **non-pipeline** attributes (signal thresholds, position sizing) reuse the cache for free.

## 6. Performance contract

| Mode | Timeframe | Max universe | Tested in CI |
|---|---|---|---|
| Event BT | daily | 5,000 | ✅ |
| Event BT | 4h / 1h | 1,000 / 500 | ✅ |
| Event BT | < 1h | — | ❌ raises |
| Vector BT | daily | 5,000 | ✅ |
| Vector BT | 4h / 1h | 1,000 / 500 | ✅ |
| Vector BT | < 1h | — | ❌ raises |
| Live | daily | 50 | smoke only |
| Live | < daily | — | ❌ raises |

**Opt-in guarantee (CI-asserted):** vector backtest of the existing single-symbol example must run within ±10% of the pre-pipeline baseline wall-clock.

## 7. Built-in factors (v1)

| Factor | Formula |
|---|---|
| `Returns(window=N)` | `close.pct_change(N)` |
| `AverageDollarVolume(window=N)` | `(close * volume).rolling_mean(N)` |
| `SMA(window=N)` | `close.rolling_mean(N)` |
| `RSI(window=N)` | standard Wilder RSI |
| `Volatility(window=N)` | `log_returns.rolling_std(N) * sqrt(periods_per_year)` |

All other factors mentioned in #438's original draft (`MACD`, `BollingerBands`, `EWMA`, `VWAP`, `MaxDrawdown`) are deferred. Users can subclass `CustomFactor`:

```python
class MACD(CustomFactor):
    inputs = ["close"]
    window = 26

    def compute(self, close: pl.Series) -> pl.Series:
        ...
```

## 8. Look-ahead safety

Factors operate on a Polars `LazyFrame` filtered to `datetime <= as_of` *before* any rolling op. Rolling windows are right-aligned (closed on the right). Tests must assert that injecting a future bar does not change a past factor value.

## 9. Open questions

1. **Universe declaration ergonomics.** Do we accept a callable `universe = lambda ctx: top_500_by_market_cap()` or only a static list in v1? (Proposed: static list in v1, callable in v2.)
2. **Pipeline scheduling.** Always run every bar, or honour a per-pipeline `time_unit`? (Proposed: same `time_unit` as the strategy in v1; per-pipeline scheduling in v2.)
3. **Multiple pipelines on one strategy.** Independent (each gets its own cache key) or composable (one pipeline can reference another's column)? (Proposed: independent in v1.)
4. **Float32 vs float64.** Default to float32 for memory; users opt into float64 per factor? (Proposed: yes, factor-level `dtype=` override.)

## 10. Out of code, in the order of work

1. ✅ This doc reviewed and merged.
2. Phase 1 ([#501](https://github.com/coding-kitties/investing-algorithm-framework/issues/501)) — event backtest + 5 factors.
3. Phase 2 ([#502](https://github.com/coding-kitties/investing-algorithm-framework/issues/502)) — vector + cache + benchmark.
4. Phase 3 ([#503](https://github.com/coding-kitties/investing-algorithm-framework/issues/503)) — live, gated on async CCXT fetch.
