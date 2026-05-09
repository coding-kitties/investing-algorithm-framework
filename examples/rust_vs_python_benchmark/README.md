# Python vs Rust backtest benchmark — `iaf-core` baseline

Companion benchmark for the **hybrid Python + Rust acceleration** epic
(#521) and its phase issues (#522–#526). The goal is a **reproducible
baseline** for measuring future Rust kernel speedups against the current
Python framework path.

## What this measures

| Side | What it does | What it represents |
|------|--------------|--------------------|
| **`python_bench.py`** | Runs `app.run_vector_backtests(...)` with a real `TradingStrategy`, real `CSVOHLCVDataProvider` data sources, real bundle write, real metric aggregation. | The end-user code path today. |
| **`rust_bench/`** | A standalone Cargo binary that loads the same parquet OHLCV, computes the same EMA + RSI signals, runs the same long-only execution loop with fees + slippage, **persists every order and per-bar portfolio snapshot to a per-backtest SQLite database** (mirroring the framework's native behavior), and prints throughput. **No PyO3, no framework abstractions.** | The **best-case ceiling** for what a future `iaf-core` Rust kernel could achieve. |

Both sides:

- Run the **same parameter sweep** (deterministic grid of `combos` strategies)
- Process the **same synthetic OHLCV** (geometric Brownian motion, seeded)
- Use the **same fees (0.1%)** and **slippage (0.05%)**
- Use the **same EMA / RSI math** semantics (Wilder RSI; pandas-style EMA)
- **Persist orders + portfolio snapshots to a per-backtest SQLite DB.**
  The framework already does this through SQLAlchemy; the Rust side
  uses bundled `rusqlite` writing through prepared statements inside a
  single transaction per backtest. Set `RUST_PERSIST=false` to measure
  the pure compute ceiling instead.
- **Compute the standard metric pack at the end of every backtest**
  (total return, CAGR, annual volatility, Sharpe, Sortino, max
  drawdown + duration, Calmar) over the per-bar portfolio equity
  curve. Mirrors the framework's `BacktestMetrics` so the comparison
  isn't unfairly skewed by Python having to compute Sharpe and the
  Rust side getting away with just final equity. Set
  `RUST_METRICS=false` to isolate persistence cost.

> **Honest framing:** This is *not* a "Rust vs Python language showdown".
> The Python side is intentionally measured **with full framework
> overhead** (data providers, strategy lifecycle, bundle write,
> per-backtest metric aggregation). The Rust side is intentionally
> minimal. The **gap between them is the optimisation headroom** that
> issues #521–#526 are scoped to capture by moving the hot path into a
> native PyO3 module behind the existing Python public API.

## Layout

```
rust_vs_python_benchmark/
├── README.md                       # this file
├── generate_data.py                # synthesise OHLCV (parquet + CSV)
├── python_bench.py                 # framework path
├── rust_bench/
│   ├── Cargo.toml
│   └── src/main.rs                 # reference Rust path
├── compare.py                      # render results table
├── run_benchmark.sh                # orchestrate the whole run
├── data/                           # generated; .gitignored
└── results/                        # generated; .gitignored
```

## Prerequisites

- Python 3.10+ with the framework installed (`pip install -e ../..` from
  the repo root, or `pip install investing-algorithm-framework`).
- Rust toolchain (`rustup` + stable `cargo`). The first
  `cargo build --release` pulls down `polars` and friends and may take
  several minutes.
- ~500 MB free disk for synthetic data at the default 10y × 5 symbols.

## Run

```bash
# default: 10y of hourly bars, 25-strategy sweep, single Python worker,
# Rust persists to SQLite (apples-to-apples with the framework path)
./run_benchmark.sh

# bigger sweep
COMBOS=100 ./run_benchmark.sh

# more years and parallel Python workers
YEARS=20 PY_WORKERS=4 ./run_benchmark.sh

# pure-compute Rust ceiling (no DB writes) — useful to isolate how much
# of the gap is SQLite I/O vs strategy lifecycle / metric overhead
RUST_PERSIST=false ./run_benchmark.sh
```

The script:

1. Generates `data/*.parquet` + `data/*.csv` if missing.
2. `cargo build --release` for `rust_bench/` if missing.
3. Runs `python_bench.py` and writes `results/python_bench.json`.
4. Runs `rust_bench` and writes `results/rust_bench.json`.
5. Prints a side-by-side table via `compare.py`.

## What the parameter grid looks like

EMA short ∈ {10, 15, 20, 25, 30}
EMA long ∈ {50, 75, 100, 150, 200}
RSI period ∈ {7, 14, 21}
RSI oversold ∈ {25, 30, 35}
RSI overbought ∈ {65, 70, 75}

Constraint: `ema_long > ema_short`. Picked deterministically.

## Strategy logic (identical on both sides)

- **Buy** when EMA-short crosses **above** EMA-long *and* RSI < oversold.
- **Sell** when EMA-short crosses **below** EMA-long *and* RSI > overbought.
- Long-only, single position per symbol.
- Fill at **next bar's open** with slippage; fees on entry and exit.
- Equal capital allocation per symbol.

## Caveats / known divergences

These are intentional and acceptable for a baseline benchmark:

- **EMA seeding:** pandas' `ewm(span=p, adjust=False)` and the Rust
  textbook EMA agree from the second sample onwards but differ on the
  very first value. The downstream signal divergence is in the noise
  for any sweep with realistic warmup.
- **RSI initialisation:** the Rust impl seeds Wilder's average from
  the first delta; pandas uses an EWM seeded similarly but with a
  slightly different ramp-up. Equivalent after `~3 × period` bars.
- **Param-grid sampling:** the Python side uses NumPy's `default_rng(0)`,
  the Rust side uses a small xorshift seeded with `0xDEAD_BEEF_CAFE_BABE`.
  The *distribution* of params is matched, the exact ordering is not.
  This does not affect throughput numbers.
- **Metrics:** both sides compute the standard metric pack (total return,\n  CAGR, annual volatility, Sharpe, Sortino, max drawdown + duration,\n  Calmar) over the equity curve. The Python side runs the **full**\n  framework `BacktestMetrics` + `BacktestSummaryMetrics` pipeline\n  (which has a longer tail of metrics: rolling Sharpe, exposure ratio,\n  trades per day, win/loss ratio, ...). Issue #523 will port the\n  metric kernel; the Rust pack here is the subset that drives 95% of\n  user decisions and is enough to make the timing comparison honest.
- **Bundle I/O:** the Python side writes `.iafbt` bundles for every
  backtest (issue #524 will port the writer). The Rust side does not
  write bundles. This is a deliberate inclusion of framework overhead
  on the Python side — it's part of what users actually pay today.

## Using this as a regression baseline

After each milestone in the iaf-core epic lands, re-run this benchmark
and append the result to `results/history.md` (or wherever you track
release benchmarks). Targets per phase:

| Phase | Issue | Expected impact on the Python column |
|-------|-------|--------------------------------------|
| Metric kernel | #523 | `metrics` portion of per-backtest cost ↓ ~10× |
| Bundle I/O    | #524 | bundle-write portion ↓ ~5× |
| Streaming pipeline | #525 | `recalculate_backtests_in_directory` (separate harness; same ratio applies) |
| Vector engine | #526 | indicator + signal + execution loop ↓ ~30–50× |

The Rust column is the asymptote.
