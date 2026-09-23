# Optional Rust Kernels

Source-installable PyO3 backend for `ConfluenceCard.evaluate_series`. Python is
still the default; installing this package does not automatically enable Rust.
The same extension also contains an experimental netting execution core
described below. It is not a strategy compiler or a complete replacement engine.

## Event Broker Prototype

`EventBroker` is an experimental, unintegrated in-memory accounting prototype.
It supports cash reservations, FIFO entry-fill lots, SELL/COVER reservations,
partial fills, cancellation, deposits and cumulative fee correction. Side codes
are BUY=0, SELL=1, SHORT=2, COVER=3. `fill` takes the fee for that fill;
`update_fee` takes the corrected cumulative order fee. Fees are quote currency.
Position amounts are settled units; subtract reserved units to obtain available
long units. Read methods return detached snapshots.

`EventBroker(cash, hedge=True)` keeps long and short legs independent, including
exit reservations, fills and cancellation. NETTING permits a flip while the
old leg is fully reserved for exit. `trade(id)` and `order_allocations(id)`
expose detached accounting read models reflecting partial closes and late fee
corrections; trade reads still scan historical allocations.

It does not replace the Python event broker or remove SQL calls. There are no
Context adapters, Python hook yields, TP/SL evaluation, native scheduling, public
backend switch or explicit trade selection. It retains complete
history. Fills and fee corrections stage affected records before committing,
preserving atomicity without cloning unrelated broker history. Fee corrections
still scan historical allocations, and retained history remains unbounded.
Do not infer bounded memory or speed improvements from these kernel tests.

The Python event backend separately archives orders, trades, allocations and
risk rules using temporary payload files and bounded-cache SQLite indexes.
That storage change does not integrate this native broker or bound its history.
See the [archive scope and validation](../../docs/design/backtest-streaming-storage-todo.md#python-accounting-archive-2026-09-21).

After compact metric optimization, 72 fresh-process comparisons show no
consistent Rust runtime or memory advantage. With Python metrics fixed, long
EMA takes 2.041 s in Python versus 2.110 s with Rust execution; long RSI takes
2.102 versus 2.072 s. Ranges overlap. Rust metrics are slower in these samples.
All optional event kernels give a 5.4% lower median (7.033 to 6.652 s), but
overlapping ranges do not establish a reliable speedup. Peak worker RSS is
essentially unchanged. All execution digests match exactly within each workload.
The earlier approximately 2.4x improvement was Python metric processing, not
Rust; keep Python defaults unless the target workload demonstrates a benefit.
See the [current paired benchmark](../../docs/design/backtest-streaming-storage-todo.md#python-versus-rust-after-compact-metrics-2026-09-21)
and the [current delivery summary and prioritized open work](../../docs/design/backtest-streaming-storage-todo.md#current-delivery-summary).

Python accounting was corrected before further integration: SELL profit/closure
now occurs at fill, and quote fees debit cash. Existing SQL ledgers require
reconciliation; old backtest checkpoints must be rerun. See the
[accounting migration notes](../../docs/design/backtest-streaming-storage-todo.md#accounting-migration-before-native-integration).

## Build and Use

From the repository root, with Rust/Cargo and a platform C linker installed:

```sh
poetry run python -m pip install ./native/confluence
```

The isolated build installs Maturin and builds a release wheel. The main package
keeps its Poetry build backend. The local wheel was verified with Cargo 1.87.0,
Python 3.12.14 on macOS arm64. The extension targets Python's 3.10+ stable ABI;
the CI matrix below covers additional platforms and interpreter versions.
Its remote results and the declared minimum Rust version remain unverified.
No automatic optional dependency extra is provided.

```python
result = card.evaluate_series(indicator_frame, backend="rust")
result_with_fallback = card.evaluate_series(indicator_frame, backend="auto")
default_python_result = card.evaluate_series(indicator_frame)
```

`rust` raises on a missing/incompatible extension or unsupported input. `auto`
falls back to the existing pandas implementation in those cases, which can still
reject custom expressions it does not support. Invalid frames, missing columns
and runtime kernel failures remain errors. `auto` is not a performance heuristic;
it may select Rust even when pandas would be faster.

## CI, Wheels and Releases

The reusable `.github/workflows/native.yml` runs Rust tests, rustfmt and strict
Clippy on Linux, macOS and Windows. It builds `cp310-abi3` wheels for Linux
x86_64/aarch64, macOS Intel/Apple Silicon and Windows x86_64. Linux wheels use
Maturin's manylinux audit/repair. Each wheel is installed without a compiler
fallback on Python 3.10, 3.12 and 3.13, alongside a built framework wheel.

An isolated `python -I native/confluence/tests/wheel_smoke.py` checks installed
distribution ownership, semantic versions, broker accounting and exact
confluence parity. The broader parity selection covers vector execution,
drawdowns, order accounting, event fills and callback scheduling. It imports
the native module unconditionally before tests, so an absent extension fails
instead of silently skipping. A separate job builds, installs and imports a
wheel rebuilt from the source distribution. Pure-Python fallback tests remain
in the normal framework suite.

Local macOS arm64/Python 3.12 wheel installation, source rebuild, smoke tests
and the 70-test/215-subtest parity selection pass. The GitHub matrix is
configured but has not yet run; other platforms are not claimed verified.

Publishing is gated in `.github/workflows/publish.yml`:

- Framework tags must be `v<VERSION>` or `<VERSION>` matching root metadata.
  Python and native checks must pass before the framework publishes using
  the existing `PYPI_TOKEN` secret.
- Native tags must be `native-v<VERSION>`, matching both native metadata files.
  Native checks must pass before the exact wheel/sdist artifacts are published.
  An ordinary framework release never republishes the native version.
- Native publication also uses the existing `PYPI_TOKEN` repository secret.
  It must have permission to publish `iaf-confluence-native`; creating the
  package for the first time requires an account-wide token.
- Publishing requires a GitHub release marked published, not merely pushing
  a tag. No release or version bump is performed by a normal CI run.

Consumers can install the optional distribution with
`python -m pip install iaf-confluence-native` after it has been published.
Unsupported platforms may build the source archive and require Rust plus a
C linker. Installing the package does not enable Rust backends automatically.

## Eligibility and Semantics

- Built-in comparisons, BETWEEN, crossings, AllOf, AnyOf, AtLeast and Not;
  primary and secondary groups, scores, requirements and vetoes.
- Referenced columns must have pandas `float64` or nullable `Float64` dtype.
  Integer, boolean, float32, object, Arrow-backed and other columns fall back or
  raise. Unreferenced columns do not affect eligibility. No implicit integer
  conversion is performed, preventing precision loss beyond 2**53.
- Definition constants must serialize as finite JSON numbers; integer constants
  beyond +/-2**53 are rejected. Null, string, boolean and nonfinite predicate
  constants are unsupported. Expression nesting is limited to 64 levels.
- `confluence-vector-v1` matches pandas batch semantics, not scalar short-circuit
  evaluation: every compound child affects availability. NaN/NA is unavailable;
  infinities in columns are valid values. Unavailable rows have NaN score and
  false qualification. Group and score summation order is preserved without
  fast-math; JSON float parsing uses exact roundtripping.
- Input rows must already be chronological. Each call starts fresh history;
  crossing expressions are unavailable on the first row. For chunked evaluation,
  prepend the previous chunk's last input row, then discard that overlap result.
  No hidden cross-call state is retained. The original index is preserved.

## Ownership and Costs

Python serializes the public card definition once per API call and uses a
process-local LRU cache (128 definitions) of immutable compiled expression trees.
Column names resolve to numeric slots during compilation. This JSON is the
existing card interchange format, not the typed canonical evidence-record format.
Compilation/cache lookup does not run once per row. Cache capacity bounds entry
count, not total definition bytes; definitions remain caller-controlled.

Each referenced column becomes little-endian f64 Python bytes, then an owned Rust
vector. Nullable conversion can allocate another temporary. The GIL is released
only after copying inputs; no Python pointers or callbacks are used during native
evaluation. One native thread evaluates the batch; no thread pool is created.
Scores and boolean status bytes are copied into Python-owned buffers and exposed
through NumPy/Pandas. Python retains buffer ownership for the result lifetime.
Bad native buffer shapes raise ValueError. Compilation errors become
`NativeConfluenceUnsupported` in the Python adapter; runtime errors propagate.

This is deliberately not Arrow zero-copy. Memory is O(rows * referenced columns)
plus outputs and the compiled definition, with temporary copies. Callers choose
frame sizes; there is no streaming sink or byte-budget enforcement. The kernel
returns aggregate score/status only, not per-rule traces, bitsets or records.

## Verification and Measurements

```sh
cargo test --manifest-path native/confluence/Cargo.toml
cargo clippy --manifest-path native/confluence/Cargo.toml --all-targets -- -D warnings
poetry run python -m unittest tests.domain.models.test_confluence_native tests.domain.models.test_confluence tests.domain.test_backtest_records -q
poetry run python -m scripts.bench_confluence_native --rows 4000 --rules 32 --repeats 5
poetry run python -m scripts.bench_confluence_native --rows 100000 --rules 32 --repeats 5
```

Native Python tests skip when the optional extension is absent; fallback tests
still execute. Build the extension before using the suite as native parity proof.
The benchmark includes definition lookup, conversions, FFI and DataFrame output;
it checks exact parity after every timed call. On the verified local build,
4,000 rows/32 rules took 18.883 ms pandas vs 2.064 ms Rust (9.15x), while 100,000
rows took 37.679 ms vs 38.140 ms (effectively tied, Rust slightly slower).
These synthetic batch results are not full-backtest or recording benchmarks.
See [the progress document](../../docs/design/backtest-streaming-storage-todo.md#phase-7-rust-hot-paths)
for environment, cold-call costs and remaining gates.

## Shared Risk Metrics

Rebuild the wheel to enable the `drawdown-v1` kernel. It computes raw and
cash-flow-adjusted drawdown series, maximum losses and durations, plus TWR equity
compounding. Other metrics stay Python; the event loop is not rewritten in Rust.

```python
from investing_algorithm_framework.services.metrics.generate import create_backtest_metrics

metrics = create_backtest_metrics(
  run, risk_free_rate=0.027, metrics_backend="rust",
)
```

Low-level `VectorBacktestService.run` and `EventBacktestService.run` also accept
`metrics_backend`. This option is independent of vector `execution_backend` and
is not yet forwarded through public app/sweep configuration. `python` remains
the default; `rust` requires supported inputs and the rebuilt wheel; `auto`
falls back for unsupported inputs or unavailable native support.

Inputs are finite float/NumPy float64 or Python integers within +/-2**52, with
Python datetime timestamps sharing a timezone object. Python sorts snapshots
and restores their timestamps; Rust owns copied whole-history arrays and releases
the GIL. This is neither streaming nor zero-copy. No metric approximation or
fast-math is used.

Three-repeat measurements show no clear benefit from the metric port alone.
The combined vector execution/risk-metrics median was 1.465 s versus 1.551 s
Python on a 650-day BTC/DOT workload, with overlapping ranges. The 30-day event
comparison does not establish a speedup: its native-assisted metric phase was
slower. See the [full benchmark and reproduction commands](../../docs/design/backtest-streaming-storage-todo.md#shared-native-risk-metrics-2026-09-20)
for all six combinations, exact parity checks and limits.

## Experimental Event Fill Selection

The wheel also exports `event-fill-v1`, a pure OHLCV trigger/fill selector.
Rebuild the wheel after updating native sources. With an existing strategy and
study configured for the event engine:

```python
from investing_algorithm_framework import BacktestRunConfiguration

results = app.run_backtest(
  strategy=strategy,
  study=study,
  run_configuration=BacktestRunConfiguration(
    event_fill_backend="rust", continue_on_error=False,
  ),
)
```

`event_fill_backend` is event-only and forwarded to spawned workers. `python`
is the default; `rust` requires the extension and supported inputs; `auto`
falls back on missing/incompatible native support or unsupported inputs.
`IAF_BACKTEST_EVENT_FILL_BACKEND` is accepted by configuration `from_env()`.
Installing the wheel alone does not enable it. Backend choice is not persisted
automatically as run provenance, and existing checkpoints can still be reused;
use a fresh output directory or disable checkpoints for a comparison.

MARKET/LIMIT/STOP/STOP_LIMIT and BUY/SELL/SHORT/COVER decisions preserve candle
order and the inclusive update boundary. Python immediately persists triggers
and applies fills through the existing evaluator, retaining custom blotter
pricing, partial amounts, fees, accounting and hook order. Already-triggered STOP
orders retain the Python evaluator's limit-search behavior; this is parity, not
a change to trading semantics.

The adapter accepts Polars datetime columns (ms/us/ns), compatible Python
datetime order updates and finite float/int prices (integers within +/-2**53).
Datetime/Open/Low/High are required; Volume is optional. Unsupported inputs are
validated before trigger/fill side effects. One order's timestamp/low/high
arrays are copied per call; Rust releases the GIL while searching. This is not
zero-copy, multi-order batching, native broker state, native scheduling or a
complete Rust event loop. SQL-backed accounting remains Python.

Three repeated 30-day BTC/DOT runs had exact Python/native result and event
bundle parity. Medians were 10.009 s Python versus 9.460 s native-assisted, with
overlapping 9.213-10.049 s and 9.439-10.950 s ranges. Only nine native selector
calls occurred per run: **no speedup or memory improvement is established**.
See [measurements and commands](../../docs/design/backtest-streaming-storage-todo.md#event-fill-benchmark-2026-09-20)
and the [remaining native event-core stages](../../docs/design/backtest-streaming-storage-todo.md#native-event-core-remaining-stages).

## Experimental Native Event Accounting and Risk

```python
configuration = BacktestRunConfiguration(event_state_backend="rust")
```

This strict, event-only option requires the native extension with
`EVENT_ACCOUNTING_SEMANTICS_VERSION="event-accounting-v1"` and
`EVENT_SETTLEMENT_SEMANTICS_VERSION="event-settlement-v1"`, plus
`EVENT_LIFECYCLE_SEMANTICS_VERSION="event-lifecycle-v1"` and
`EVENT_ARCHIVE_SEMANTICS_VERSION="event-archive-v2"`. Rebuild older local
extensions before using this backend. Configuration also
accepts `IAF_BACKTEST_EVENT_STATE_BACKEND=rust` through `from_env()`. It is
forwarded to spawned workers; a missing or incompatible extension fails before
execution. SQL remains the default. Runtime errors propagate without replaying
an event through Python. Use fresh checkpoints to compare backends.

Archive v2 supports indexed exclusive `created_at_gt` order queries used by
cooldown tracking. Python and Rust archives normalize aware query timestamps
to UTC with fixed microsecond precision before scalar comparison. Older native
extensions fail preflight rather than silently skipping cooldown recording.

The actual order services use native cash/position reservation, fill, cancel
and cumulative-fee transitions. Trade services use native exit cost/gain,
allocation settlement and late-fee correction; built-in fixed/trailing stop-loss
and take-profit methods use native state transitions for long and short rules.
Python persists those results before dispatching the existing lifecycle hooks.
There is one archive-backed ledger, not a Python ledger mirrored into the
stateful `EventBroker` prototype. Native transitions retain no execution history.

SELL/COVER settlement now uses one native batch plan per fill: allocation
consumption, explicit COVER priority followed by FIFO spillover, weighted SELL
prices, trade fees/gains and position/portfolio exit aggregates. Python supplies
ordered candidates and persists the returned plan; Rust retains no history.

The Rust backend now also owns scalar candidate filtering/order in a disk-backed
SQLite index (rusqlite with bundled SQLite), FIFO/explicit SELL reservation
plans, lifecycle phase ordering and market-order/trade traversal. Equal-time
FIFO heap ordering matches Python exactly. The native controller re-queries
open trades after fills and evaluates take profits before stop losses.
Timestamp traversal and native candle selection are enabled automatically,
irrespective of the independent fill/schedule selector defaults. Failures are
propagated immediately, without replaying the tick through Python.

Python still adapts repository queries, decodes/persists records, handles
relationship filters, prepares schedules/market data, updates risk reservations,
checks trade closure, reconciles late-fee aggregates and invokes custom
callbacks/models. This is **not Python-free execution** or an entirely native
data plane. Native index cursors keep queries of up to 128 matched offsets in
a bounded buffer without creating a temporary table. Larger queries retain
that prefix and spool the remainder to temporary disk. A transient 129th row
detects overflow; consumption buffers at most 128 rows. Prepared SELECT
statements are reused. There is no duplicate all-history native broker.
Active result sets, per-trade relationships, metric arrays, temporary disk and
total RSS are not hard bounded.

Local validation: 148 tests plus 432 subtests, 25 Rust tests, exact randomized
reservation/settlement comparisons, per-phase failure ordering, native index
streaming/interleaved updates, hedge/risk hooks and worker/resume parity.
Six alternating fresh-process 30-day BTC/DOT EMA runs had identical execution
and saved-bundle digests. Python median was 6.842 s (6.155-7.829); Rust was
6.580 s (6.309-6.838). Whole-worker peak medians were 456.8/462.0 MiB.
Ranges overlap: no reliable runtime or memory gain is established. See the
[controller measurements](../../docs/design/backtest-streaming-storage-todo.md#native-query-reservation-and-tick-controller-2026-09-22).

The subsequent bounded-query optimization passes 38 Python tests plus 287
subtests and 27 Rust tests. Empty/five-row query microbenchmarks take about
26x/16x less time; three before and three after event runs preserve exact
results but do not establish an end-to-end speedup. See the
[query measurements](../../docs/design/backtest-streaming-storage-todo.md#bounded-native-query-fast-path-2026-09-22).

## Experimental Event Schedule Traversal

The independent `BacktestRunConfiguration(event_state_backend="memory")` option
uses Python accounting and archive-backed repositories across event services.
Verified cases avoid ORM tick queries; the sparse archive index still uses
SQLite. Historical measurements below predate the archive and native-accounting
integration above. The stateful native broker remains a separate prototype;
integrated transitions do not allocate its all-history maps. See the
[memory-state results and limits](../../docs/design/backtest-streaming-storage-todo.md#event-memory-state-benchmark-2026-09-21).

`BacktestRunConfiguration(event_schedule_backend="rust")` opts into Rust
timestamp traversal. `python` remains the default; `auto` falls back only during
preflight for a missing/incompatible extension or unsupported timestamps.
`IAF_BACKTEST_EVENT_SCHEDULE_BACKEND` is supported by `from_env()`. Selection is
forwarded to sequential runs and spawned event workers, independently of
`event_fill_backend`. Strict extension checks run before backtest execution.

Python still generates and sorts the complete schedule. Rust validates strictly
increasing integer microsecond timestamps and calls Python once per tick. The
original datetime keys and payloads drive Context clock updates, broker/risk
evaluation, tasks, strategies, scheduled functions, resource guards, and snapshot
flushes in their existing order. Callback failures propagate without replay or
fallback; live loops are unchanged. Python datetime keys are supported, with
naive keys interpreted as UTC for traversal and original values kept in Context.

This is **only native traversal**, not native broker ownership or a complete
native simulation. The GIL is retained for Python callbacks, all schedules are
still materialized, and SQL-backed tick services remain unchanged. Backend
selection is not stored automatically as provenance; record experiment settings
and use fresh checkpoints for comparisons.

A fresh corrected-accounting benchmark (three alternating runs per backend,
30-day EMA BTC/DOT) produced identical result and bundle digests, five trades
and 31 snapshots. Python's median was 9.882 s (9.391-10.279 s); native traversal's
was 10.039 s (9.172-10.239 s). **No significant speedup is established.** A
separate profiled run counted 4,169 SQL statements inside 361 ticks in each
backend. See the [measurement and next gate](../../docs/design/backtest-streaming-storage-todo.md#event-traversal-benchmark-2026-09-21).

## Experimental Vector Execution Loop

`VectorBacktestService.run(..., execution_backend="rust")` now executes the
supported trading-state loop in Rust. This is independent of the confluence
`backend` argument. Reinstall the local wheel after updating native sources:

```sh
poetry run python -m pip install --force-reinstall ./native/confluence
```

Service-level usage with an existing configured data provider:

```python
from investing_algorithm_framework.infrastructure.services.backtesting.vector_backtest_service import VectorBacktestService

service = VectorBacktestService(data_provider_service)
result = service.run(
    strategy=strategy,
    backtest_date_range=backtest_date_range,
    portfolio_configuration=portfolio_configuration,
    execution_backend="rust",
)
```

Execution selection is also forwarded through backtest run configuration and
vector workers. Defaults are unchanged. At the service boundary,
`python` is the default, `rust` requires eligibility and the extension, and `auto`
falls back only for missing/incompatible extensions or unsupported inputs. Native
runtime errors propagate. Backend selection is not automatically persisted as
run provenance; callers should record it with their experiment configuration.

### Supported Subset

- NETTING, with long/short entries, exits and opposite-signal flips.
- Static sizing or dynamic built-in fixed/percentage sizing. Dynamic sizing
  requires CPython 3.12+ for compensated float summation; tested on 3.12.14.
- Standard percentage/fixed fees and percentage slippage below 100%, plus
  scheduled deposits mapped to the first bar at or after their timestamp.
- Multiple symbols sharing capital, in the exact symbol
  iteration order supplied by Python. The vector service now supplies lexical
  symbol order for deterministic spawned runs; Rust never sorts independently.
  Rerun old checkpoints because prior set ordering could change shared-capital
  outcomes across processes.
- Built-in symbol/portfolio cooldowns, with buy/sell/any triggers and blocks.
- Fixed take-profit and stop-loss rules, evaluated before signals. TP wins
  ties. As in the Python vector engine, these close the whole position and
  ignore `sell_percentage` and rule `side` in netting mode. Covers are not
  cooldown-rule-gated, and flips do not record their closing leg as a cooldown
  event. These are parity constraints, not new trading semantics.
- Finite positive float64 prices and nonnullable boolean signal arrays after
  the existing Python alignment step. Python-sized integers above 2**53 are
  rejected for initial/static capital rather than silently rounded.
- No hedge mode, scaling, custom sizing/cost/risk models or trailing rules.
  Simultaneous long/short entry signals are rejected,
  rather than redefining the Python engine's current behavior for those bars.

Unsupported scenarios raise `NativeExecutionUnsupported` in strict mode; use
`auto` to retain Python execution. Python vector mode itself does not implement
trailing TP/SL; use event mode for trailing rules.

### Execution and Ownership

The `netting-accounting-v5` kernel receives owned copies of per-symbol
little-endian f64 price bytes, packed signal bytes, sizing/cost specifications,
deposits and compiled cooldown/risk rules. The original `run_static_netting`
function and `static-netting-v1` version remain available for compatibility.
One signal byte encodes buy/sell/short/cover in bits 0/1/2/3. One native call
traverses all bars and symbols, computing fills, fees, slippage, cash, reserved
capital, position values and realized gains. A native lifecycle replay computes
portfolio and position snapshots in original trade order. The GIL is released
for both passes; they create no workers
or Python callbacks. Sell/cover precedence, same-bar entry suppression and
rejection outcomes match the supported Python path.

Rust returns a `NettingResult`: ordered `Execution` records, last reported trade
prices, and packed little-endian f64 snapshot buffers. Portfolio rows contain
cash, total value, realized gain and cash flow; position rows contain signed
amount, cost, long/short amount and long/short cost in input-symbol order.
Execution sides 0..3 are buy/sell/short/cover; reasons 0..9 encode execution,
missing long/short position, insufficient capital, already-in-position,
open-short-position, flip, cooldown rejection, TP and SL. `has_fill` distinguishes
an accounting record from a signal-only outcome. These are internal versioned
results, not persisted evidence records.

Python materializes domain objects without recomputing fills or P&L. It retains
signal preparation, final position objects, most metrics and reporting. NumPy scalar
types are preserved for snapshot values and last prices where the Python engine
uses them, because downstream summation can otherwise change by one bit. No
per-bar FFI is used. This is not a fully native backtest engine.

Input and output copies remain. The entire event list and snapshot history are
materialized in Rust and then Python; memory grows with input size, symbol count,
signal count and snapshot count. This is not a
bounded streaming loop, zero-copy interface or cross-call resumable state.

### Execution Verification

```sh
poetry run python -m unittest tests.infrastructure.services.backtesting.test_vector_snapshot_events -q
poetry run python -m scripts.bench_vector_snapshot_events --native-loop --bars 4000 --symbols 3 --repeats 3
poetry run python -m scripts.bench_vector_snapshot_events --native-loop --bars 8000 --symbols 3 --repeats 3
```

Tests compare complete normalized results including trades, orders, positions,
snapshots, signal outcomes and metrics. Coverage includes randomized signals,
capital contention, zero-sized entries, same-bar exits, open positions, strict
rejection, fallback, empty native batches and malformed buffers. Accounting tests
cover costs, static/dynamic sizing, deposits, fee-exhausted entries and flips.
Control tests cover cooldown scope/sides/boundaries, TP/SL ties and combined
randomized scenarios. Exact execution parity also passed with `PYTHONHASHSEED=0`
and `1`. With the wheel installed, 74 focused Python tests (execution plus
confluence/records), 58 vector scenario tests and seven Rust tests pass.
Python lint and strict Clippy pass.

On macOS 26.6.2 arm64, Python 3.12.14, pandas 2.3.3 and Cargo 1.87.0, the
three-symbol cycling benchmark measured these warmed medians over five
alternating repeats with the cooldown/TP/SL-capable v5 core.
Exact parity was checked outside timing:

| Bars | Trades | Python | Rust | Elapsed reduction |
| --- | --- | --- | --- | --- |
| 4,000 | 3,000 | 1.474052 s | 1.270264 s | 13.8% |
| 8,000 | 6,000 | 2.798443 s | 2.472607 s | 11.6% |

Timings include conversion, native execution, event reconstruction, snapshots
and metrics; they exclude app/pool startup, bundle I/O and indicator preparation.
These are local measurements of static zero-cost cycling signals, not guaranteed
gains or a benchmark of every supported feature. Real BTC/DOT EMA and RSI/EMA
strategies with active risk rules were also measured over 30/365/650-day windows:
36 exact-parity runs, 650-day EMA execution 1.611 s Python / 1.536 s Rust;
RSI/EMA effectively tied. Bundle saving cost 1.6-1.9 s separately. See
[representative profiling and storage measurements](../../docs/design/backtest-streaming-storage-todo.md#representative-profiling-2026-09-19)
for process-tree RSS, worker transfer, event-engine observations and caveats.
The optional local bounded writer is not integrated into the native engine.
Cross-platform packaging and whole-sweep memory acceptance remain unverified.
