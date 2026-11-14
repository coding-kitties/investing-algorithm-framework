# Backtest Streaming Storage and Rust Readiness

Status: shared compact metrics, disk-backed result histories, streamed bundle
saving, optional Rust kernels, archive-backed native accounting/risk and release
automation are implemented to the scope below. This is **not a complete Rust
event engine or a hard-bounded-memory implementation**. Platform CI is configured
but has not yet been verified on GitHub.
Last updated: 2026-09-23.

## Current Delivery Summary

This summary and the open-work list are the current status. Dated measurements
and phase checklists below retain the history and wider target scope; a local
component passing does not imply its whole-engine acceptance gate has passed.

| Area | Delivered and verified locally | Boundary still open |
| --- | --- | --- |
| Naming and records | Canonical `DecisionTrace` APIs, compatibility aliases, versioned language-neutral records, definition hashes and reference adapters | Full producer/retention/query integration |
| Accounting correctness | Fill-time SELL/COVER settlement, FIFO allocations, reservations, partial fills, cancellation, cumulative quote-fee corrections and hook ordering | Existing live ledgers need reconciliation; old checkpoints must be rerun |
| Python execution | Optional run-local repositories, no ORM tick queries in verified cases, deterministic processing; accounting histories spooled with sparse SQLite indexes | Python accounting remains available; active/matched result sets and supplied write batches are not capped |
| History storage | Event snapshot and order/trade/allocation/risk archives; read-only disk-backed result histories and eight metric series; streaming reads and indexed scalar filters | Individual record sizes, temporary disk and file-descriptor budgets are not capped |
| Recording and handoff | Bounded signal recording, local synchronous chunk writer, manifests and atomic publication, event-worker bundle-path handoff | Not an integrated streaming sink for every event/vector history |
| Bundle saving | Lazy serialized records, batched metric Parquet, streamed MessagePack/compression and atomic replacement | Bundle open/merge and other result transport paths remain eager |
| Metrics | One source scan into compact scalar rows, shared trade summaries and cached DataFrame/daily/monthly/yearly calculations, exact numeric parity | Temporary scalar rows and arrays are still O(n); arbitrary user scans still decode |
| Integrated Rust kernels | Optional confluence/vector/metric kernels; event scalar query index, SELL reservation plans, lifecycle/market traversal, fill selection, accounting/risk and batched settlement | Python record/data adapters, relationship filters, risk reservation updates, closure and late-fee aggregates remain; native vector coverage is limited |
| Rust broker prototype | FIFO lots, long/short legs, partial fills, reservations, late fees and detached trade/allocation reads without whole-state rollback copies | Unintegrated, retains all history, no authoritative Context/service/risk path |
| Measurement | Fresh-process runtime and RSS harness, exact result digests, real EMA/RSI workloads, 50-algorithm SQL/memory recording/resume sweep, 72 post-optimization Python/Rust comparisons | No enforced 16 GB acceptance; no consistent current Rust runtime or RSS advantage |
| Quality and distribution | All 28 CI lint findings fixed; Rust tests/fmt/Clippy; platform wheel and source-build workflows; isolated installation/parity tests; gated publishing | Remote matrix, minimum Rust version and PyPI Trusted Publisher setup unverified |

Latest Python data-path checks: 234 tests plus 177 subtests across conversion,
data providers, repositories, accounting, hooks and worker/resume behavior.
Latest native controller checks: 148 tests plus 432 subtests, 25 Rust tests,
strict Clippy, rustfmt and framework flake8 passed.
Earlier compact-metric/release checks: 728 regression tests plus 59 subtests;
the native selection
passed 70 tests plus 215 subtests in both the existing and a fresh environment;
20 Rust tests, strict Clippy, rustfmt, full framework flake8 and actionlint passed.
The release wheel and source archive built; source rebuilding, clean installation,
`pip check` and three isolated smoke tests passed on macOS arm64/Python 3.12.
Test selections overlap and these counts do not mean the full platform suite ran.

### What Is Actually Faster?

- **Long event archive decoding:** twelve alternating fresh-process runs with
  profiling and RSS sampling disabled reduced the 365-day median from 40.104
  to 36.159 seconds (9.8%) and the 650-day median from 74.371 to 66.636 seconds
  (10.4%). Exact results, bundle digests and saved metrics match. These are
  Python decoder improvements on the Rust event backend, not a Python/Rust
  engine comparison. See the long-event profile below.
- **Python archive reads and conversion:** six alternating fresh-process runs
  reduced 30-day EMA event execution median from 8.439 to 6.945 seconds (17.7%),
  with exact execution/bundle parity. Peak RSS was essentially unchanged.
  See [the data-path benchmark](#python-data-path-optimization-2026-09-21).
- **Python metric optimization:** 45 fresh-process runs preserved exact execution
  digests. Long EMA execution improved from 6.034 to 2.539 seconds; long RSI from
  5.531 to 2.228 seconds. Metric-phase RSS fell about 7 MiB; whole-worker peak
  remained similar. Event metric generation improved, but total event runtime
  did not. These are not Rust speedups.
- **Earlier direct Python/Rust comparison:** Rust reduced 650-day EMA execution
  time by about 7.2%, with no demonstrated RSI, event-runtime or RSS benefit.
  This comparison predates compact metric inputs.
- **Current comparison after compact metrics:** 72 fresh-process runs preserve
  exact execution results. With Python metrics unchanged, Rust execution takes
  2.110 versus 2.041 seconds for long EMA and 2.072 versus 2.102 seconds for long
  RSI: effectively tied with overlapping ranges. Rust metrics do not improve
  the long workloads. All optional event kernels give a 5.4% lower median,
  but ranges overlap; no consistent runtime or memory advantage is established.
  See [the current benchmark](#python-versus-rust-after-compact-metrics-2026-09-21).

### Long Event Profile and Decoder Optimization (2026-09-22)

The 365-day BTC/DOT EMA event profile contains 4,381 ticks, 42 trades and 366
snapshots. Before optimization, cumulative times were 23.638s for strategy
indicators, 14.789s for Polars-to-pandas conversion, 22.795s for repository
dispatch and 12.488s for archive decoding (195,536 calls). Cooldown bookkeeping
scans all orders every tick and accounted for 12.339s, overlapping repository
and decode time. These nested profile times must not be added together.
Metrics took 0.198s and bundle saving 0.266s in the clean baseline run;
persistence was not the dominant cost on this workload.

Fresh detached archived objects now populate scalar state with one dictionary
update instead of per-field SQLAlchemy committed-value calls. Relationship
collections still use SQLAlchemy instrumentation. Tests verify initially clean
state, subsequent dirty tracking/save behavior, detached mutation isolation,
interleaved writes, relationships, accounting and risk hooks. No record cache
or retained history was added. The follow-up profile reduced archive decoding
to 3.713s and cooldown scanning to 4.905s; indicator and conversion costs stayed
near their prior levels. Profile timings identify costs, not speedup claims.

The runtime comparison uses three samples per decoder/duration, reversing
decoder order on alternate repeats, each in a fresh process:

| Duration | Baseline median (range), seconds | Optimized median (range), seconds |
| --- | --- | --- |
| 365 days | 40.104 (36.993-40.242) | 36.159 (34.121-36.457) |
| 650 days | 74.371 (73.969-76.451) | 66.636 (62.011-67.220) |

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --days 365 650 --strategies ema --backends event \
  --event-state-backends rust --archive-decoders baseline optimized \
  --no-rss --repeats 3 --output /tmp/iaf-long-decoder-paired.json
```

Raw local measurements: `/tmp/iaf-long-decoder-paired-20260922.json` and
`/tmp/iaf-year-profile-clean-{before,after}-20260922.json`. The harness now
disables RSS sampling during profiles, retains the top 100 functions and counts
native adapters automatically enabled by Rust state. Use `--no-rss` for timing:
the 10ms process-tree sampler materially perturbed this macOS workload. Earlier
sampler-enabled before/after medians were noisy and do not establish a gain.
RSS-free timings make no memory claim; the hard 16 GB gate remains open.

Validation: 73 tests plus 345 subtests passed across archives, accounting,
trade hooks and worker/backtest options. Production/test-file lint passed;
the benchmark retains pre-existing long lines. This is one EMA strategy over
two durations, not broad strategy coverage: the harness skips RSI event cases.
Next profile-guided targets are repeated frame conversion, the full-history
cooldown query and relationship filtering. Arbitrary user indicator costs
remain outside the framework optimization made here.

### Shared Conversion and Cooldown Filtering (2026-09-23)

Implemented for the applicable event and vector paths:

- The shared provider converter uses serial Arrow conversion for frames of
  at most 10,000 rows and skips deduplication copies for unique timestamps when
  constructing a datetime index. Non-indexed outputs retain the prior index
  behavior. Large frames retain the original threaded/deduplication path after
  measurement showed the small-frame approach regressed at 100,000 rows.
  Outputs remain independently mutable; no frame cache was added.
- Event cooldown recording passes its existing exclusive timestamp watermark
  into the order query. SQL filters before ORM loading; Python and Rust archives
  use timestamp indexes before decoding. UTC/fixed-microsecond normalization
  preserves comparisons across offsets and subsecond boundaries. Existing
  equal-timestamp exclusion, metadata filtering and symbol scope are unchanged.
  This reduces historical decoding, not the number of per-tick queries.
- The Python vector loop skips initial buy/sell cooldown scans when that side
  has no signals. Same-bar post-fill checks are unchanged. Vector already records
  exits directly, so there is no event-style order-history scan to remove.
  The Rust vector loop and hedge-specific cooldown logic remain unchanged;
  both vector backends receive shared provider conversion improvements.

Native event preflight now requires `event-archive-v2`. The local virtual
environment was rebuilt; other environments need to reinstall `native/confluence`.
No native release was published.

The benchmark now supports `--preparation-paths baseline optimized` and
`--real-vector-data`. The former restores the immediately preceding converter
and unfiltered event order scan; it does **not** restore old vector cooldown
gating. The latter uses the real CSV-backed application for vector runs, instead
of the earlier prebuilt-pandas test adapter that bypasses conversion. Counters
verify 11,812 conversions and 4,335 watermark queries in the event case, versus
only 5 EMA / 7 RSI conversions per vector case.

Thirty alternating fresh-process, RSS-free, unprofiled year-long BTC/DOT runs
(three samples per mode/workload) preserved exact execution digests, bundle
round trips and saved metrics. Median execution seconds:

| Workload | Previous preparation | Optimized preparation |
| --- | --- | --- |
| EMA event, Rust state | 32.185 | 27.440 |
| EMA vector, Python | 5.380 | 5.221 |
| EMA vector, Rust | 5.110 | 5.194 |
| RSI vector, Python | 7.595 | 8.093 |
| RSI vector, Rust | 7.613 | 8.144 |

Event time fell 14.7%, with non-overlapping ranges (32.032-32.895s versus
27.240-27.558s). Vector results are mixed, including slower RSI samples; these
measurements do **not** establish a vector speedup or isolate the vector gating
change. The converter microbenchmark improved at 1/600/10,000 rows; its impact
is small when conversion happens only a few times per run. No memory claim.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --days 365 --strategies ema rsi --backends event python rust \
  --event-state-backends rust --real-vector-data \
  --preparation-paths baseline optimized --no-rss --repeats 3 \
  --output /tmp/iaf-preparation-year.json
```

Raw local report: `/tmp/iaf-preparation-year-20260923.json`. The harness still
skips RSI event cases. Earlier synthetic-provider vector saved-metric differences
remain a separate issue; they were absent in these real-provider runs.

Validation: 320 tests plus 103 subtests (providers, conversion, cooldowns,
repositories, deterministic P&L, scaling, hedge, hooks and worker options),
27 Rust tests, rustfmt and strict Clippy passed. Touched production-file lint
passed. Full-framework lint still reports four unrelated long lines in the
stop-loss/take-profit rule files. Editor dependency-resolution warnings remain,
while virtual-environment runtime checks pass. Conversion tests cover the size
threshold, duplicate/null timestamps, datetime units, exact index/dtype output
and mutation isolation; archive tests prove old rows are excluded before decode;
a vector regression forbids cooldown queries on signal-free bars.

## Open Work, Prioritized

### Before a Supported Native Release

- [ ] Run the configured GitHub matrix: Linux x64/arm64, macOS Intel/arm64 and
  Windows x64 wheels, installed checks on Python 3.10/3.12/3.13, plus the normal
  framework suite. Repair any platform-specific failures; local actionlint is
  not a substitute for executing CI.
- [ ] Verify the declared Rust minimum version, or update it to a tested minimum.
- [ ] Configure the `pypi-native` environment and PyPI Trusted Publisher, then
  review package versions and release artifacts. Native releases use
  `native-v<VERSION>`; ordinary Python releases must not republish native wheels.
- [ ] Resolve or explicitly specify/test vector bundle normalization of
  `equity_curve`, `yearly_returns`, `best_year` and `worst_year`. Execution parity
  passes, but those saved metrics still differ in all benchmark input modes.
- [x] Rerun current-code Python/Rust runtime and peak-memory comparisons with
  compact metrics: 48 vector and 24 event runs, exact per-workload parity.
- [ ] Set explicit throughput/overhead acceptance targets. The current benchmark
  does not justify advertising a general Rust speedup.

### Before Claiming Bounded Memory

- [x] Spool Python event execution orders, trades, allocations and risk rules;
  preserve tested FIFO settlement, late fees, detached queries and hooks.
- [ ] Bound active/matched result sets, individual trade relationship graphs
  and write batches. The disk archive alone is not a whole-execution bound.
- [ ] Replace remaining whole-history metric arrays with exact incremental or
  bounded multi-pass calculations. Compact scalar inputs alone are not a bound.
- [ ] Stream bundle loading/merging, vector finalization and remaining result
  handoff paths; keep coordinator indexes/checkpoints bounded.
- [ ] Integrate bounded decision/snapshot output in both engines, including
  vector traces; audit schedules, market arrays, recorded values and metadata
  separately from history buffers.
- [ ] Define oversized-record, temporary-disk, file-descriptor and total worker
  budgets. Exercise slow writers, disk-full failures, crashes and retries through
  the integrated engine path, not only the standalone writer.
- [ ] Run a representative 50-algorithm workload under an enforced 16 GB budget
  with an agreed machine reserve and increasing history length. The completed
  30-day/two-worker sweep proves parity/resume, not this hard-memory gate.

### To Complete the Native Engine and Analysis Design

- [x] Route actual event services and built-in risk rules through native
  transitions over one archive-backed ledger; callbacks observe persisted state.
- [x] Batch SELL/COVER allocation consumption and exit aggregate calculations
  in Rust, with explicit COVER priority, FIFO spillover and exact service parity.
- [x] Move indexed scalar candidate queries, FIFO/explicit SELL reservation
  planning, tick phase ordering and market traversal into Rust.
- [ ] Move remaining relationship filtering, risk-allocation bookkeeping,
  cancellation release bookkeeping, trade lifecycle mutations and late-fee
  aggregates into a native data plane. Current Rust control still calls Python
  data/persistence adapters; it is not a Python-free engine.
- [ ] Move eligible scheduler advancement and risk evaluation onto shared market
  arrays. Rust traversal still uses a Python-built schedule, per-order candle
  conversion and Python data/service adapters.
- [ ] Extend native execution eligibility to the remaining hedge, scaling,
  trailing-risk and custom-model cases, or define explicit supported fallbacks.
  Integrated event hedge partial-fill/cancel parity passes; this does not extend
  native vector eligibility or move custom Python models into Rust.
- [ ] Connect native record emission to bounded storage/finalization, and verify
  compute-only versus compute-plus-recording costs and exact Python parity.
- [ ] Finish retention policies (qualified, executed-trade-linked, sampled and
  diagnostic), including delayed fills, deterministic sampling and equal engine
  semantics without changing required metrics or trading outcomes.
- [ ] Finish lazy range/column/trace queries, plotting and portable chunk/manifest
  export with legacy `.obtf` compatibility and relocation-safe references.
- [ ] Expose remaining service-only backend selectors through public app/sweep
  configuration and define backend provenance/checkpoint compatibility.

No commit, version bump, tag or publication has been performed. The open native
engine and hard-memory work is separate from shipping accurately scoped optional
kernels after their distribution gates pass.

## Bounded Native Query Fast Path (2026-09-22)

Native archive selection previously created, populated and dropped a temporary
SQLite table for every query, including empty results. It now probes at most
129 matching offsets with a cached prepared SELECT. Results of up to 128 rows
stay in the cursor buffer with no temporary table. For larger results the first
128 rows are retained and only the remainder is spooled. This avoids decoding
and spooling the prefix twice; the remainder query still performs its ordering
and offset work, so other query shapes need their own measurements.

No public configuration or extension contract changes. The row buffer and
statement cache are bounded, not a history cache. Matched identities, ordering
and offsets retain selection-time snapshot semantics. The existing Python
archive revision guard continues to load current payloads after interleaved
writes. This is not a whole-engine memory bound.

Validation: 38 tests plus 287 subtests across archive operations, accounting,
risk-hook parity, spawned workers/resume and native smoke checks; 27 Rust tests,
rustfmt, strict Clippy, test lint and whitespace checks pass. Cursor tests cover
0/1/127/128/129/300 rows, snapshot isolation, fresh cached query parameters,
ordering and temporary-table cleanup. The installed-distribution location check
was excluded from local smoke tests; remote platform CI was not run.

Local release-extension query microbenchmark: seven samples, each consuming
500 identical queries, with exact output assertions. Baseline was measured
before rebuilding; results are not interleaved baseline/optimized pairs.

| Matched rows | Before median (ms/500 queries) | After median (ms/500 queries) |
| ---: | ---: | ---: |
| 0 | 11.970 | 0.454 |
| 5 | 13.888 | 0.867 |
| 128 | 33.763 | 11.504 |
| 129 | 34.936 | 29.864 |
| 1000 | 190.334 | 184.262 |

Three fresh-process 30-day EMA BTC/DOT Rust event runs before rebuilding and
three afterward preserve identical full-result digests and saved bundles.
Execution median was 6.946 s before (6.851-7.810) and 7.064 s afterward
(6.941-7.486). The after median is about 1.7% higher, with overlapping ranges.
**No end-to-end speedup is established**, despite the local query savings.
The before/after blocks are not a randomized crossover experiment.
Raw reports: `/tmp/iaf-query-before-20260922.json` and
`/tmp/iaf-query-after-20260922.json`.

## Native Query, Reservation and Tick Controller (2026-09-22)

The subsequent query fast path above supersedes the always-spooled cursor
description in this historical increment.

`event_state_backend="rust"` now selects the following integrated paths:

- A Rust-owned rusqlite index replaces Python sqlite3 for accounting archive
  scalar filtering, deterministic ordering, offset lookups and updates. One
  authoritative disk index is used, not a shadow native ledger. Query cursors
  spool matching offsets to temporary disk and buffer at most 128 rows; both
  main and temporary SQLite page caches are configured to 64 KiB. The existing
  revision guard preserves updated payload reads during interleaved writes.
- Native FIFO/explicit SELL reservation plans compute selection and remaining
  availability. FIFO duplicates Python heap tie behavior, rather than replacing
  it with a stable sort. Repeated explicit references accumulate sequentially.
- A native lifecycle controller sequences preparation, evaluation, tasks,
  strategies, scheduled functions and finalization. Empty strategy lists and
  exception boundaries retain the reference behavior, with no Python replay.
- Native market traversal handles pending-order iteration, re-queries trades
  after fills, marks prices, then requests take-profit and stop-loss processing
  in that order. Native timestamp traversal and candle selection are enabled
  automatically for this backend; independent Python selector defaults do not
  disable them.

Python still supplies record encoding/decoding and persistence, relationship
filters, schedule and market-data preparation, custom strategies/fill models,
risk reservation bookkeeping, closure mutations and late-fee aggregate updates.
The control loops moved, but their adapters are not a fully native data plane.
Selected candidate lists and individual records remain unbounded. No hard
whole-engine memory or Python-free execution claim is made.

New extension capabilities `event-lifecycle-v1` and `event-archive-v1` are
required at preflight in addition to the existing contracts. Rebuild older
extensions. The wheel bundles SQLite; the native archive schema is private
scratch storage, not a new persistent public format.

Validation: 148 tests plus 432 subtests across the event loop, archive,
accounting, risk hooks and workers/resume; 25 Rust tests and strict Clippy pass.
New coverage checks each lifecycle failure boundary, post-fill candidate
refresh, exact randomized FIFO heap ordering, sparse IDs, multi-page native
query iteration, interleaved updates and cleanup after index closure. Native
archive tests prohibit Python sqlite3 connections. Framework lint and actionlint
pass. Installed native smoke tests pass locally; the remote wheel matrix and
the declared Rust 1.74 compiler remain unverified. New dependency metadata does
not declare a higher Rust minimum.

Six alternating fresh-process 30-day EMA BTC/DOT runs preserve identical full
result digests and bundle round trips (361 ticks, five trades, four risk hooks):

| Backend | Execution median (s) | Range (s) | Whole-worker peak median (MiB) |
| --- | ---: | ---: | ---: |
| Python archive | 6.842 | 6.155-7.829 | 456.8 |
| Rust query/reservation/tick controller | 6.580 | 6.309-6.838 | 462.0 |

Ranges overlap and native RSS is higher: no reliable speedup or memory gain is
established. Raw report: `/tmp/iaf-native-controller-20260922.json`. Measurements
precede the follow-up reduction of the native temporary-table page cache to
64 KiB; that adjustment has regression coverage but no separate benchmark.

## Native Batch Exit Settlement (2026-09-22)

Historical settlement increment; the controller section above supersedes its
candidate-query, reservation and orchestration ownership notes.

The strict Rust event backend now computes a complete SELL/COVER fill plan in
one native call. Rust consumes the supplied allocations, prioritizes explicit
COVER trades before FIFO spillover, computes weighted SELL close prices and
updates trade fees/gains. Native finalization computes the exit's position cost
and portfolio gain, size and revenue. Python persists the plan before the
existing final lifecycle callbacks; no duplicate native ledger is introduced.

Python still queries and sorts candidates, reserves entries/exits, updates risk
allocations, checks closure, reconciles late-fee aggregates, persists records
and orchestrates market ticks and custom callbacks. Input vectors and plans are
proportional to selected candidates/allocations, not hard bounded. This is a
further native engine increment, not completion of the native event loop.

Preflight now also requires `event-settlement-v1`; rebuild older extensions.
Runtime native errors still propagate without Python replay. Defaults and
public backend configuration are unchanged.

Validation: 131 tests plus 245 subtests cover accounting, risks, hooks, archive
reads and workers/resume. Coverage includes 100 randomized exact comparisons of
both planners and final aggregates, repeated allocations for one trade, explicit
short priority with FIFO spillover, hedge partial cancellation, late fees,
nonfinite inputs and incompatible extension rejection. Actual service tests
assert planner invocation. All 25 Rust tests, rustfmt, strict Clippy and framework
flake8 pass. The installed-module smoke selection passes; the isolated remote
wheel/platform matrix has not been rerun here.

Six alternating fresh-process 30-day EMA BTC/DOT event runs used identical
optimized Python data paths. All full-result digests and bundle round trips
match exactly: 361 ticks, five trades and four stop-loss hooks each.

| Backend | Execution median (s) | Range (s) | Whole-worker peak median (MiB) |
| --- | ---: | ---: | ---: |
| Python archive | 6.532 | 6.283-6.591 | 460.0 |
| Rust accounting/risk and batch settlement | 6.257 | 6.243-6.272 | 459.8 |

The Rust median is about 4.2% lower in this small workload, with essentially
unchanged RSS. This compares current Python and Rust backends, not old versus
new Rust settlement in isolation; it does not establish a general speedup.
Raw report: `/tmp/iaf-native-settlement-20260922.json`.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --days 30 --strategies ema --backends event \
  --event-state-backends memory rust --repeats 3 \
  --output /tmp/iaf-native-settlement-20260922.json
```

## Python Data-Path Optimization (2026-09-21)

Three measured Python hot paths have been optimized without changing backend
defaults or adding production configuration:

- Archive selection retrieves payload offsets with its original SQLite query,
  removing one lookup per decoded row. A revision guard restores ID lookups if
  writes occur during iteration, preserving live reads after interleaved updates.
- Public archive reads return already-detached decoded objects instead of
  recursively cloning them again. Resident state and pending archive graphs
  still use defensive copies; eager children and nested metadata remain isolated.
- Polars-to-pandas conversion avoids an extra full-frame copy and skips parsing
  already-typed datetime columns. String parsing, duplicate removal, timezone,
  timestamp units, nulls, indexing and source isolation retain exact semantics.

Validation: 234 tests plus 177 subtests passed across conversion, providers,
repositories, accounting, risk hooks and worker/resume. A ten-row archive scan
now executes one index query instead of eleven. Retained-memory and detached
mutation tests pass; no resident history cache was introduced.

Six serial fresh-worker runs alternated benchmark-only restoration of the
previous implementations with the optimized paths. All six full-result digests
and saved-bundle round trips match exactly on 30-day BTC/DOT EMA event backtests.

| Python path | Execution median (s) | Range (s) | Whole-worker peak median (MiB) |
| --- | ---: | ---: | ---: |
| Previous implementations | 8.439 | 8.204-9.078 | 460.3 |
| Optimized | 6.945 | 6.918-7.814 | 459.9 |

This is about **17.7% less execution time on this workload**, not a universal
speed guarantee or a Rust improvement. RSS is effectively unchanged. Raw report:
`/tmp/iaf-python-data-paths-20260921.json`.

```sh
.venv/bin/python -m scripts.bench_backtest_streaming \
  --days 30 --strategies ema --backends event --event-state-backends memory \
  --python-data-paths baseline optimized --repeats 3 \
  --output /tmp/iaf-python-data-paths-20260921.json
```

The baseline switch is confined to the benchmark harness. The earlier rough
percentage-complete estimates were not a measured work breakdown. These changes
finish this measured Python read/conversion increment, not all possible Python
optimization: matched sets, per-trade graphs, metric arrays, bundle load/merge
and the enforced whole-machine memory target remain open above.

## Integrated Native Accounting and Risk (2026-09-21)

`BacktestRunConfiguration(event_state_backend="rust")` now selects native
order cash/position transitions, exit cost/gain and allocation fee calculations,
and built-in fixed/trailing long/short risk decisions. The actual event services
persist native outputs into the same archive-backed ledger used by `memory`;
hooks and Context read that state. Native transitions retain no history and do
not instantiate the separate all-history `EventBroker` prototype.

The selector is forwarded to spawned workers and supported by
`IAF_BACKTEST_EVENT_STATE_BACKEND` through `from_env()`. It requires the native
extension with `event-accounting-v1` semantics before execution and propagates
failures without Python replay. Defaults are unchanged. Backend choice is not
checkpoint provenance; use fresh output paths for comparisons.

At this stage Python still selected FIFO/explicit trades, performed aggregate
updates and orchestrated persistence, lifecycle callbacks, custom models and
market ticks.
The subsequent batch-settlement increment above moves exit consumption and
exit aggregates to Rust; other orchestration remains in Python.
This is an integrated native accounting/risk backend, not the entire proposed
native event core. Archive matched sets and per-trade relationships, metric
arrays, schedules, temporary disk and total RSS remain outside a hard bound.

Validation: 71 tests plus 139 subtests across accounting, archive repositories,
risk hooks, workers/resume and configuration; 23 Rust tests, rustfmt, strict
Clippy and framework flake8 pass locally. Risk coverage includes 64 differential
long/short fixed/trailing paths. Hedge normalization also exposed and fixed a
shared archive bug: numeric loading must not invoke netting-only legacy setters.
CI now includes native event hook/worker/preflight and accounting wheel checks;
the remote platform matrix remains unexecuted locally.

Six alternating fresh-process 30-day EMA BTC/DOT runs preserved identical full
result and saved-bundle digests, 361 ticks, five trades and four stop-loss hooks:

| Backend | Execution median (s) | Range (s) | Whole-worker peak median (MiB) |
| --- | ---: | ---: | ---: |
| Python archive | 7.706 | 7.590-7.964 | 459.6 |
| Rust accounting/risk archive | 7.639 | 7.517-11.272 | 460.5 |

**No reliable runtime or memory improvement is established.** Both retain the
same archive and Python orchestration costs. Zero ORM tick queries does not
mean zero SQLite calls. Raw report: `/tmp/iaf-native-accounting-20260921.json`.

```sh
.venv/bin/python -m scripts.bench_backtest_streaming \
  --days 30 --strategies ema --backends event \
  --event-state-backends memory rust --repeats 3 \
  --output /tmp/iaf-native-accounting-20260921.json
```

## Python Accounting Archive (2026-09-21)

The experimental `event_state_backend="memory"` now spools execution orders,
trades, allocations and risk rules after repository operations, in addition to
snapshots. Portfolio and position state remains resident. Accounting payloads
are private temporary-file records; sparse IDs map to offsets through per-table
temporary SQLite B-trees with a 64 KiB page-cache target and mmap disabled.
There is no resident per-history-row Python index. These SQLite calls are not
counted by the SQLAlchemy instrumentation: **zero ORM queries is not zero SQL**.

Scalar status/order/trade/position filters run before decoding. Ordered order
exports use disk-side sorting; portfolio and trade-order relationship filters
stream decoded rows. `get_all` still materializes its matches. Eager order/risk
lists for an individual trade and supplied write batches can be large. Updates
append replacement payloads, so disk usage includes obsolete versions. This
is scratch storage, not crash recovery, transactional accounting or a disk cap.

Validation: **129 tests plus 73 subtests** passed across repositories, event
memory options/resources, risk hooks and corrected order/trade accounting.
Coverage includes partial fills, cancellation and late fees against the native
prototype, exact SQL/memory results, sibling risk-rule deactivation on closure,
detached child edits, sparse IDs, duplicate order links and scope cleanup.
An open-order query decodes only its one match among 1,001 orders. Portfolio
history scans retain fewer than five decoded rows. Growing from 100 to 1,000
order/trade pairs adds less than 256 KiB of retained traced Python allocations;
this test does not bound native memory, RSS or arbitrary record sizes.

Six fresh-process, alternating SQL/archive runs of the 30-day BTC/DOT EMA case
preserved exact execution digests and exact saved-bundle results:

| Backend | Execution median (s) | Range (s) | Whole-worker peak median (MiB) |
| --- | ---: | ---: | ---: |
| SQL | 11.606 | 11.229-11.719 | 443.4 |
| Python archive | 7.775 | 7.282-8.515 | 449.3 |

Both produce 361 ticks, with 4,169 versus zero **ORM** tick statements. The
archive is about 33% faster than SQL here; this is not a comparison with the
previous resident-memory backend and not a Rust speedup. Peak RSS did not
improve on this short workload. Parent process retention makes tree peaks
order-sensitive. Raw report: `/tmp/iaf-accounting-archive-20260921.json`.

```sh
.venv/bin/python -m scripts.bench_backtest_streaming \
  --days 30 --strategies ema --backends event \
  --event-state-backends sql memory --repeats 3 \
  --output /tmp/iaf-accounting-archive-20260921.json
```

**Historical archive-only stage:** no authoritative Rust accounting/risk
integration was added in this archive increment. The prototype still retains
all history and lacks the adapter/explicit-allocation/risk contracts needed to
replace Python service transitions without duplicating accounting or changing
callback-visible state. Python defaults remain unchanged. The earlier native
benchmarks below predate this archive change and are historical measurements.

## Python Versus Rust After Compact Metrics (2026-09-21)

This rerun supersedes the earlier direct Python/Rust timings for the current
implementation. The extension was rebuilt from current sources through a release
PEP 517/Maturin build. Both sides use the same shipped compact metric inputs.
No runtime implementation or backend default was changed for this measurement.

The existing harness ran 48 vector cases (30/650 days, EMA/RSI, all four
execution/metric backend combinations) and 24 event cases (30-day EMA, all eight
metric/fill/schedule combinations). Each configuration has three fresh-worker
repetitions with alternating backend order. Benchmarks ran serially, without
concurrent builds or test suites. This is a local sample, not a controlled
multi-machine significance study or a 50-worker capacity test.

Environment: macOS 26.6.2 arm64, Python 3.12.14, NumPy 2.2.6, pandas 2.3.3,
PyArrow 24.0.0. BTC/DOT 2-hour CSV hashes are recorded in both JSON reports.
RSS is sampled every 10 ms and is not a hard maximum. Vector execution includes
simulation, result construction and metrics but excludes CSV preparation,
process startup and bundle I/O. Event execution times the public backtest call,
including its internal preparation/finalization/saving. Do not compare absolute
vector and event times as if they measured identical paths.

### Vector Results

Median execution seconds; headings are **execution backend / metrics backend**.
Rust metrics accelerate only eligible risk calculations, not all metric code.

| Workload | Python / Python | Rust / Python | Python / Rust | Rust / Rust |
| --- | ---: | ---: | ---: | ---: |
| EMA 30d | 0.4015 | 0.2988 | 0.4564 | 0.3628 |
| RSI 30d | 0.3661 | 0.4221 | 0.3976 | 0.3492 |
| EMA 650d | 2.0413 | 2.1095 | 2.4205 | 2.2341 |
| RSI 650d | 2.1020 | 2.0716 | 2.1681 | 2.2061 |

Long-window ranges and median phase/runtime memory measurements:

| Strategy | Execution / metrics | Execution range (s) | Metrics median (s) | Metric RSS (MiB) | Whole-worker peak (MiB) | Process-tree peak (MiB) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| EMA | Python / Python | 2.0343-2.4928 | 1.6834 | 329.0 | 375.4 | 709.8 |
| EMA | Rust / Python | 2.0153-3.6088 | 1.7624 | 330.9 | 374.8 | 717.4 |
| EMA | Python / Rust | 2.2695-2.7700 | 2.0207 | 333.3 | 378.4 | 715.4 |
| EMA | Rust / Rust | 2.2269-2.4053 | 1.8904 | 334.5 | 379.7 | 719.5 |
| RSI | Python / Python | 2.0605-2.1401 | 1.7308 | 329.6 | 372.3 | 705.2 |
| RSI | Rust / Python | 1.9008-2.0794 | 1.6751 | 330.4 | 372.1 | 708.4 |
| RSI | Python / Rust | 2.0431-2.2206 | 1.8301 | 333.8 | 374.5 | 706.6 |
| RSI | Rust / Rust | 2.0702-2.2080 | 1.8705 | 334.2 | 375.7 | 717.8 |

With metrics held on Python, Rust execution's median is 3.3% slower for long
EMA and 1.4% faster for long RSI; ranges overlap. Enabling both Rust execution
and metrics is 9.4% slower for EMA and 5.0% slower for RSI in this sample.
Short EMA shows a lower Rust-execution median, but its 0.2350-0.3414 s range
overlaps Python's 0.3294-0.4901 s; short RSI is inconsistent across selectors.
This does not establish a reliable general Rust benefit. Whole-worker RSS is
essentially unchanged; native metrics add a few MiB in these long cases.

### Event Results

Python memory-state accounting is fixed across all cases. Each run has five
trades, 31 snapshots, 361 ticks, four stop-loss hooks and zero tick SQL. Selecting
Rust fills performs nine native selector calls; Rust traversal performs one
native schedule call. These are optional kernels, not an authoritative Rust
event engine. Values below are medians except the execution ranges.

| Metrics / fills / traversal | Execution (s) | Range (s) | Metrics (s) | Worker peak (MiB) | Tree peak (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Python / Python / Python | 7.0329 | 6.7896-7.2867 | 0.0970 | 459.9 | 629.5 |
| Python / Python / Rust | 6.7236 | 6.6383-6.7627 | 0.1074 | 459.6 | 756.8 |
| Python / Rust / Python | 7.1893 | 6.8612-7.5655 | 0.1375 | 458.5 | 755.9 |
| Python / Rust / Rust | 6.8123 | 6.6049-7.4126 | 0.1149 | 459.7 | 757.1 |
| Rust / Python / Python | 6.5987 | 6.2465-6.8576 | 0.1709 | 459.2 | 758.6 |
| Rust / Python / Rust | 6.6629 | 6.1576-6.6774 | 0.1358 | 459.8 | 760.5 |
| Rust / Rust / Python | 6.7246 | 6.2513-6.8562 | 0.1401 | 459.3 | 759.8 |
| Rust / Rust / Rust | 6.6518 | 6.1267-7.0852 | 0.1324 | 459.5 | 759.9 |

All enabled kernels give a 5.4% lower total median, but their execution range
overlaps the all-Python range. The metrics-only Rust case has a lower total
time despite its measured metric phase being slower, illustrating noise outside
the selected kernel. Traversal-only timings are promising in this small sample,
but not enough to establish a general speedup. Worker RSS stays about 459 MiB.
Parent allocator retention makes process-tree RSS order-sensitive; the lower
baseline tree median is not evidence that native state needs another 130 MiB.

### Parity and Reproduction

All 72 execution digests match exactly within their workload. All 24 event
bundle round trips also match. Existing vector bundle normalization differences
in `equity_curve`, `yearly_returns`, `best_year` and `worst_year` remain separate
from execution parity and occur across backend choices. Profiling was disabled.

```sh
poetry run python -m pip install --force-reinstall --no-deps ./native/confluence
poetry run python -m scripts.bench_backtest_streaming --days 30 650 --strategies ema rsi --backends python rust --metrics-backends python rust --metric-input-modes compact --repeats 3 --output /tmp/iaf-postcompact-rust-vector-20260921.json
poetry run python -m scripts.bench_backtest_streaming --days 30 --strategies ema --backends event --event-state-backends memory --metrics-backends python rust --event-fill-backends python rust --event-schedule-backends python rust --metric-input-modes compact --repeats 3 --output /tmp/iaf-postcompact-rust-event-20260921.json
```

The JSON reports retain all individual timings, phase RSS, digests, fixture
hashes and backend selections. Recommendation: retain Python defaults; select
Rust for a specifically measured eligible workload, not as an automatic speed
or memory optimization. Further performance work needs profiling of the current
dominant costs rather than assuming that enabling more Rust kernels helps.

## Default Disk-Backed Result Histories

`BacktestRun.orders`, `.trades`, `.portfolio_snapshots` and all eight
`BacktestMetrics` time series now use public `BacktestHistory` sequences by
default. Construction accepts iterables and spools one serialized record at a
time. A fixed-width disk index supports length, positive/negative indexing and
shared-storage slices. Sequential scans use bounded read buffers and detached
records, without caching decoded history. Filtered run queries scan into a new
disk-backed history; unfiltered queries return the existing history.

This is an intentional v9 change from mutable result lists:

```python
recent_trades = run.trades[-20:]
for trade in recent_trades:
  print(trade.net_gain)

snapshots = run.portfolio_snapshots.materialize()
snapshots[-1].metadata["reviewed"] = True
run.portfolio_snapshots = snapshots
```

Editing an individually retrieved record does not alter stored history.
`list(history)` and `.materialize()` explicitly allocate mutable copies.
`to_dict()` and legacy JSON saving retain their eager, JSON-friendly contract.
Copies and slices keep shared scratch files alive; files close after the last
owner is released. Each nonempty history uses two temporary file descriptors;
empty histories open none. Temporary disk usage grows with records. Scratch
files use the platform's temporary directory (`TMPDIR` where supported), must
remain writable, and are not durable checkpoints or an interchange format.
Individual record size is not capped. Standard result pickling works but its
transport buffer can still grow with the complete result.

Event result export uses repository iterators (256-record SQL pages). Bundle
save consumes lazy serialized histories, writes MessagePack incrementally and
spools metric Parquet in batches of 4,096 points before streaming compression.
Selected scalar trade metrics share one scan. Existing bundle version and
atomic replacement semantics are preserved.

Local synthetic snapshot measurement (three warm scan repetitions, median;
construction allocations measured with `tracemalloc`, not RSS):

| Rows | List retained Python bytes | Disk retained Python bytes | List scan | Disk decoded scan |
| --- | ---: | ---: | ---: | ---: |
| 10,000 | 3,766,824 | 15,667 | 0.236 ms | 35.281 ms |
| 100,000 | 37,601,472 | 11,806 | 2.418 ms | 359.252 ms |

The disk-backed scan is substantially slower than walking already-created
objects. This test measures summing `total_value`, not total backtest latency,
and excludes OS page cache/native allocator memory. Repeated arbitrary user
scans incur that cost; explicitly materialize when the working set fits RAM.

Validation: 626 tests and 181 subtests passed across metrics, histories,
bundles, event worker/resume paths and vector parity. History lifetime,
detached reads, portable locked I/O fallback, pickle transport, multi-batch
Parquet round trips and malformed-series cleanup are covered.

**Remaining limitations:** execution still retains order/trade/allocation
accounting histories; many metric helpers still sort or build full arrays and
DataFrames; bundle open and merge still decode whole documents. Vector
producers, custom signals/metadata and large records can also allocate without
a byte bound. Default disk-backed results do not establish a whole-engine RSS
limit or complete authoritative Rust event integration.

### Iteration Investigation and Release Assessment

Before the compact-input fix below, measurements on 2026-09-21 identified
repeated internal record decoding as a release-blocking performance concern,
not just an isolated list-iteration microbenchmark. This subsection records
that investigation's baseline; it does not describe current metric generation.

Using 10,000 independent copies of a real 650-day EMA run's snapshot/trade
record, five warm repetitions per operation gave these median scan times:

| Record | Existing objects in RAM | Pickled bytes in RAM, decoded to models | Disk history, decoded to models |
| --- | ---: | ---: | ---: |
| Snapshot, including two positions | 0.947 ms | 68.323 ms | 73.178 ms |
| Trade, including two orders | 0.366 ms | 225.596 ms | 246.442 ms |

RAM-held serialized bytes are almost as expensive to scan as buffered disk
history. Pickle decoding and domain reconstruction dominate these warm-cache
measurements; they do not measure cold-disk latency. Merely changing the file
buffer or retaining encoded bytes in RAM will not restore list-like speed.

Default metric generation for 72 trades and 7,802 snapshots performed 25 full
trade scans and 36 snapshot scans, decoding 280,872 snapshots. In five
alternating repetitions, median metric time was 3.603 s with disk-backed inputs
versus 1.287 s with already-materialized inputs; initial materialization took
0.061 s. Serialized metric values matched exactly. These are diagnostic
same-process timings, not fresh-process performance acceptance.

A separate service-execution comparison included one-time materialization in
the measured alternative and retained disk-backed final results. Three
alternating repetitions per 650-day BTC/DOT strategy produced:

| Strategy | Current default | Materialize metric inputs once |
| --- | ---: | ---: |
| EMA | 3.629 s | 1.684 s |
| RSI | 3.401 s | 1.549 s |

All normalized execution/result digests matched within each strategy. Timings
include vector simulation and metrics, excluding CSV loading, process startup
and bundle saving/loading. The materialized alternative was a temporary
in-process benchmark patch, is not shipped, and is not memory bounded.

The implementation below addresses repeated internal decoding while preserving
the approved read-only result contract. Arbitrary user iteration still decodes
records. A per-history decoded cache is not introduced.

### Compact Metric Inputs and Paired RSS Benchmark (2026-09-21)

Metric generation now scans each source trade/snapshot history once into a
private, run-local scalar projection. Nested orders, positions and metadata
are released after each record. Original Python/NumPy numeric types are kept
to preserve exact reduction semantics. Best/worst trades are reloaded by index
for the public result. Shared trade summaries and cached snapshot DataFrames,
daily TWR, monthly and yearly resampling avoid repeated decoding and repeated
batch calculations. Direct public helper calls retain their existing behavior.
Caches are discarded after metric generation; no cache is attached to the run.

This working set is **O(trades + snapshots), not byte bounded**. Several
calculations still create complete arrays/series. It is smaller than retaining
full nested domain graphs, but is not streaming metrics or a whole-engine cap.

The benchmark accepts `--metric-input-modes legacy compact materialized`.
`legacy` bypasses preparation and repeatedly decodes disk histories; `compact`
uses the shipped shared projections; `materialized` creates benchmark-only
full-domain lists without shared caches. Input preparation is included in
metric/execution timings. Three alternating-order repetitions per mode run in
fresh spawned workers. Vector service timing excludes CSV preparation, startup
and bundle I/O; event timing covers the public call, including internal saving.
The sampler records absolute worker and parent-plus-worker RSS every 10 ms,
including metrics, transfer, save, merge and read phases. Peaks are sampled,
not enforced limits; parent allocator retention makes tree RSS order-sensitive.

Environment: macOS 26.6.2 arm64, Python 3.12.14, NumPy 2.2.6, pandas 2.3.3,
PyArrow 24.0.0. Real BTC/DOT 2-hour CSVs and Python execution/metrics were used.
The event case uses memory state, 361 ticks, four stop-loss hooks and zero
tick SQL statements. Each cell lists **legacy / compact / materialized**
medians. Memory units are MiB; worker peak includes result serialization.

| Workload | Trades / snapshots | Execution seconds | Metric seconds | Metric-phase RSS | Whole-worker peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vector EMA 30d | 5 / 362 | 0.654 / 0.377 / 0.515 | 0.518 / 0.298 / 0.331 | 320.2 / 308.9 / 310.4 | 321.4 / 310.6 / 311.8 |
| Vector RSI 30d | 1 / 362 | 0.667 / 0.383 / 0.429 | 0.472 / 0.271 / 0.289 | 318.1 / 317.7 / 317.9 | 319.4 / 319.1 / 319.5 |
| Vector EMA 650d | 72 / 7802 | 6.034 / 2.539 / 2.767 | 5.633 / 1.924 / 2.275 | 336.4 / 328.8 / 336.7 | 368.0 / 369.4 / 371.4 |
| Vector RSI 650d | 6 / 7802 | 5.531 / 2.228 / 2.437 | 5.087 / 1.858 / 2.071 | 336.2 / 329.3 / 336.5 | 373.8 / 371.1 / 373.2 |
| Event EMA 30d | 5 / 31 | 7.211 / 7.266 / 7.231 | 0.164 / 0.102 / 0.140 | 446.8 / 447.8 / 444.5 | 459.5 / 459.9 / 458.0 |

Compact execution is 2.38x (long EMA) and 2.48x (long RSI) faster than repeated
decoding. EMA execution ranges were 5.877-6.374 s legacy and 2.195-2.990 s
compact; RSI ranges were 5.275-5.599 and 2.046-2.247 s. Metric-phase RSS is
about 7 MiB lower, but whole-worker peak is essentially unchanged. **No event
end-to-end speedup is established**: legacy and compact ranges overlap at
7.083-7.235 and 7.109-7.725 s. Tree RSS medians for legacy/compact/materialized
were 506.6/720.0/596.8 MiB (long EMA), 713.9/706.8/613.2 MiB (long RSI) and
753.6/754.6/752.6 MiB (event). Do not interpret these noisy parent-inclusive
values as a memory saving.

All 45 execution digests match exactly within their workload. Event bundle
round trips also match. Existing vector bundle normalization still changes
`equity_curve`, `yearly_returns`, `best_year` and `worst_year` in all three
modes; this measurement does not resolve that separate persistence caveat.

Reproduce from the repository root:

```sh
poetry run python -m scripts.bench_backtest_streaming --days 30 650 --strategies ema rsi --backends python --metric-input-modes legacy compact materialized --repeats 3 --output /tmp/iaf-compact-metrics-vector-20260921.json
poetry run python -m scripts.bench_backtest_streaming --days 30 --strategies ema --backends event --event-state-backends memory --metric-input-modes legacy compact materialized --repeats 3 --output /tmp/iaf-compact-metrics-event-20260921.json
```

JSON reports contain individual timings, phase RSS, fixture hashes, versions,
digests and bundle differences. These are local measurements, not hard-memory
acceptance or a new Rust-versus-Python speed comparison.

### Validation and Release Gates

The full CI command `flake8 ./investing_algorithm_framework --statistics --count`
now reports zero findings; all 28 previous findings are fixed. Local validation
passed 728 metric/history/bundle/store/worker-resume tests and 59 subtests,
plus the native parity selection (70 tests, 215 subtests), 20 Rust tests,
formatting and strict Clippy. Counts overlap between selections. Release wheel
and source builds, clean installation with `pip check`, three isolated smoke
tests and fresh-environment parity pass on macOS arm64/Python 3.12. The source
archive independently rebuilds a wheel.

The reusable native workflow adds Linux x64/arm64, macOS Intel/arm64 and Windows
x64 ABI3 wheels, installed checks on Python 3.10/3.12/3.13, and source-build
verification. Mandatory native imports prevent missing-wheel skips from passing
native validation. Actionlint passes locally. Python releases depend on Python
and native checks; separate `native-v<VERSION>` releases publish only validated
native artifacts. See the [native release setup](../../native/confluence/README.md#ci-wheels-and-releases).

The GitHub platform matrix has not run locally, the declared minimum Rust
version is not verified, and hard-memory acceptance remains open. Neither
these gates nor compact metrics complete the authoritative Rust event engine.
No commit, version bump, tag or publication was performed.

## Accounting Migration Before Native Integration

Shared accounting was corrected before resuming the native event port, by
explicit user decision. The Python event/live order service now debits cumulative
quote-currency fee deltas once, including late corrections. SELL placement
reserves units without closing trades or realizing P&L. Execution settles FIFO
cost and proportional entry/exit fees at the actual fill price; cancellation
releases only the unfilled reservation. COVER settlement uses matched short-lot
cost and fees. Close/update hooks run after fill accounting, not allocation.
Pending exit reservations can make available units zero while the trade remains
OPEN and its position cost remains nonzero. Already-filled SELL creation also
settles immediately. Fee corrections update realized allocations and portfolio
P&L without replaying close hooks.

Migration requirements:

- Rerun backtests into fresh checkpoints/output directories. Existing saved
  results are not rewritten and can contain the old fee/close semantics.
- Do not resume an existing SQL allocation ledger created under placement-time
  accounting. It requires explicit reconciliation/rebuilding; this change does
  not migrate historical allocations or live exchange state automatically.
- Consumers must not use `available_amount == 0` as proof of trade closure.
  Check status; reserved but unfilled trades remain OPEN.
- Risk-trigger hooks now precede close hooks for resting exits. Closure requires
  a later eligible fill, including when the last signal is near the window end.
- Fees are cumulative, finite, nonnegative quote-currency amounts. Missing fee
  currency means quote currency. Base-asset/third-token fees must be converted
  upstream; unsupported reported currencies raise instead of debiting an
  unrelated cash balance. Exchange-side execution is not rolled back by a local
  validation error; live callers must reconcile such reports explicitly.

`native/confluence/src/event_broker.rs` is an experimental accounting prototype:
cash, orders, reservations, FIFO fill lots, cancellation, deposits and cumulative
fee correction. Focused tests compare it with corrected Python accounting.
It is **not wired into Context, the event runner, risk rules, workers, snapshots
or scheduling** and does not remove per-tick SQL. It retains full histories.
Fill and fee mutations now stage only affected records before validation and
commit, instead of cloning the entire broker and lot history for rollback.
Unrelated order/allocation storage is retained in place; overflow rejection
leaves state unchanged. Fee reconciliation still scans the allocation history,
so this is not a bounded-memory or constant-time implementation.
Detached trade/allocation reads and separate hedge-leg accounting are now
available in the prototype. Explicit trade selection and callback yielding
are still missing. The three native event stages below remain incomplete.

## Event Memory State Benchmark (2026-09-21)

`BacktestRunConfiguration(event_state_backend="memory")` selects experimental
run-local repository state; `sql` remains the default. Environment configuration
supports `IAF_BACKTEST_EVENT_STATE_BACKEND=memory`. Selection is forwarded to
sequential runs and spawned workers. Context, order/trade/risk services,
snapshots and final result creation share one context-local state per algorithm
and window. Reads stay detached and the scope is reset on exit, including
exceptions. Unsupported populated repository filters raise explicitly.

This is an intermediate Python backend, **not native EventBroker integration**.
At the time of this earlier measurement it retained complete accounting
histories; the later Python Accounting Archive section supersedes that limit.
Portfolio and position snapshots are now spooled to private temporary files
after each repository operation, using a disk-resident fixed-width ID index.
Detached reads now copy
only eagerly mapped relationships (trade orders/risk rules and snapshot
positions), rather than lazy back-references into allocation history. Writes
still handle supplied relationship graphs and merge edited eager children.
New rows are normalized once, not once per mapped column. Neither bounded
retained history nor a universal memory limit is established.
Custom code issuing SQL directly bypasses this backend. Setup, external data
providers and final result storage can still use SQL. Live defaults are unchanged.

### Snapshot Retention Increment

The memory backend no longer keeps every portfolio/position snapshot graph in
`EventMemoryState.rows`. Snapshot payloads and ID offsets live in separate
temporary files, closed on normal scope exit and exceptions. Reads rebuild
detached models and eager child relationships. Updates append replacement
records; saving a stale parent merges only edited columns and children.
Creating position snapshots separately updates the archived parent relationship.
The spool is private, process-local scratch storage, not a checkpoint or bundle
format; it only reads payloads written by the same run.

Filtered queries stream records before collecting matches. `count`, `exists`
and `find` do not retain scanned history. `get_all` still materializes requested
results, and each repository write retains its supplied batch until flushing.
Disk usage grows with history and updates. No snapshot-byte admission limit,
full-engine RSS bound, or performance improvement is claimed.

Validation: canonical snapshot weak references are released after flushing;
a 1,000-record count retains fewer than five scanned model objects at once.
Detached reads, child edits, separately created children and exceptional file
cleanup are covered. Repository, event configuration/worker/resume and risk-hook
suites pass: **42 tests and 58 subtests**, including exact SQL/memory results
with SQL forbidden throughout the active memory scope.

**Unfinished at this snapshot-only stage:** authoritative Rust event
accounting/risk integration, accounting-history archiving and bounded
metrics/result/bundle finalization. The later accounting archive addresses
history retention, not the native integration or whole-engine memory gates.

Parity fixes found during integration:

- Merged `metadata_json` must refresh transient order/trade metadata, just as
  SQL reload does. Otherwise pending TP/SL rules can disappear from fills.
- SQL-loaded portfolio snapshots now get empty instance metadata instead of
  serializing SQLAlchemy's class-level `MetaData()` object. Snapshot metadata
  still has no SQL column; this is not a metadata persistence migration.

Fresh 30-day EMA BTC/DOT results, three alternating fresh-process repeats per
backend, Python fill/schedule/metrics backends:

| State | Median execution | Range | SQL inside 361 ticks |
| --- | ---: | ---: | ---: |
| SQL | 9.752 s | 9.210-10.677 s | 4,169 |
| Memory | 6.465 s | 6.459-6.612 s | 0 |

Execution took approximately **34% less time (1.51x speedup)** on this workload.
The benchmark times the public event run, including internal preparation and
persistence. Harness end-to-end medians were 21.619 s versus 18.459 s, including
fresh-process startup, transfer and saving. Peak process-tree RSS stayed roughly
745-766 MiB: no memory improvement is established.

All six result digests and saved-bundle round trips matched exactly: five trades,
31 snapshots and four stop-loss hooks per run. A separate integration test
forbids SQL during the entire active memory scope, including snapshot flush and
result creation. Worker parity and checkpoint resume also pass. Use fresh
checkpoints for comparisons; backend selection is not persisted as provenance.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --backends event --strategies ema --days 30 --repeats 3 \
  --event-state-backends sql memory \
  --output /tmp/iaf-event-memory-verified-20260921.json
```

Trailing-stop and fixed take-profit fixtures now compare exact SQL/memory
results plus ordered callback observations (status, available amount, gains,
fees and current price). Both exercise a real close after the risk trigger.
Broader memory-backend scenario coverage (hedge, deposits and arbitrary custom
callbacks), bounded history storage, and authoritative native accounting/risk
integration remain open. The measured improvement must not be attributed to
Rust scheduling or accounting.

### Completed 50-Algorithm Acceptance

The fresh 30-day EMA BTC/DOT sweep completed with two workers, recycling workers
after eight tasks. All 50 saved-result digests match across SQL/memory state and
recording off/on, and all four checkpoint resumes pass. Each case contains 250
trades and 1,550 snapshots; each recorded case contains 18,050 signal reports.

| State | Signal Recording | Execute/Save, s | Peak Process-Tree RSS, GiB | Resume, s |
| --- | --- | ---: | ---: | ---: |
| SQL | Off | 288.5 | 1.216 | 2.30 |
| SQL | On | 307.8 | 1.183 | 2.64 |
| Memory | Off | 226.8 | 1.289 | 1.71 |
| Memory | On | 203.1 | 1.285 | 2.15 |

This is one acceptance sample per case, not an alternating repeated timing
study. Some regression tests ran concurrently on the machine; do not attribute
the timing differences precisely to the backend or recording. RSS sums the
coordinator and its workers, not unrelated test processes. Memory state used
slightly more peak RSS here, despite the reduced transient read copies.
This verifies 50 queued algorithms with two workers, not 50 simultaneous runs,
a long-history memory bound, or an enforced 16 GB whole-machine limit.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --sweep --backends event --event-state-backends sql memory \
  --algorithms 50 --days 30 --workers 2 \
  --sweep-directory /tmp/iaf-memory-acceptance-20260921 \
  --output /tmp/iaf-memory-acceptance-20260921.json
```

Use a new sweep directory when reproducing; existing directories are rejected.

### Copy Reduction and Reproducibility

- [x] Avoid copying lazy relationship history on each Python memory read.
  A regression test attaches 100 allocations to an order and verifies the read
  copies one model, not all 101. Nested metadata stays detached; saving an
  edited eager child still updates authoritative state.
- [x] Remove whole-broker rollback clones from Rust prototype fills and fee
  corrections. Stage changed lots, the current allocation list, fee changes,
  order and position before committing. Native tests check failure atomicity
  and stable storage addresses for unrelated retained history.
- [x] Use lexical symbol order for both vector execution paths. A set previously
  made shared-capital processing and result order depend on process hash seeds.
  Fresh checkpoints are required: simultaneous-symbol outcomes may differ from
  an older run's arbitrary order. This does not change event strategy ordering.
- [x] Extend the sweep harness with `--event-state-backends sql memory`, comparing
  exact per-algorithm saved-result digests across state backends as well as
  recording modes, with checkpoint resume for each case.
- [x] Complete the 50-algorithm, 30-day, two-worker SQL/memory parity and resume
  sweep, including signal recording. This is workload acceptance only.
- [x] Spool portfolio/position snapshots and stream filtered repository reads.
- [ ] Evict archived orders, trades and allocations while preserving
  historical queries, late fee corrections and exact final metrics.
- [x] Replace default result histories with disk-backed sequences and stream
  bundle saving with batched metric encoding.
- [ ] Replace whole-bundle loading/merging and remaining eager finalization
  paths with bounded batch reads.

The copy changes reduce transient allocation amplification, not the size of
the authoritative retained history. Bounded signal batches and worker recycling
remain useful controls, but do not establish a full-engine memory ceiling.

Three alternating read-copy repeats, measured with `tracemalloc` after source
history construction:

| Attached Allocations | Full-Graph Peak, Bytes | Eager-Only Peak, Bytes | Models Copied Before/After |
| --- | ---: | ---: | ---: |
| 100 | 95,640 | 4,587 | 101 / 1 |
| 10,000 | 8,949,144 | 4,587 | 10,001 / 1 |

At 10,000 allocations this reduces temporary traced allocation from 8.53 MiB
to 4.48 KiB. Median traced copy time is 1.0164 s versus 0.0003205 s; tracing
overhead makes these diagnostic timings, not an engine speedup estimate.
Canonical history, native allocations and process RSS are outside this measure.

The final synchronous diagnostic-writer check wrote and read exactly 1,048,576
records in 128 chunks, using 8,192-row batches and zstd level 3. Peak admitted
batch was 2,318,344 bytes (2.21 MiB); sampled write RSS rose 20.7 MiB above
baseline, and read RSS rose 42.2 MiB. Write/read took 10.481/0.891 s; stored
size was 281,962,238 bytes. This verifies the standalone writer, not full-history
engine streaming. Report: `/tmp/iaf-writer-final-20260921.json`.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --writer --rows 1048576 --repeats 1 --writer-batch-rows 8192 \
  --writer-levels 3 --writer-modes sync --writer-retention diagnostic \
  --output /tmp/iaf-writer-final-20260921.json
```

| Control | What It Limits | What Remains Unbounded |
| --- | --- | --- |
| Eager-only Python reads | Lazy back-reference copies | Requested eager graph and canonical history |
| Staged Rust mutations | Unrelated state copies for rollback | Affected allocations and retained history |
| Signal recorder | 256 KiB payload buffer, 1,024 rows, 64 KiB admitted record | Producer's original report and transient encoding |
| Synchronous Arrow writer | 8 MiB admitted batch, 8,192 rows, 16 MiB encoded chunk | Caller allocations and codec/native allocator overhead |
| Event snapshot flush and disk spool | Loop batch and resident repository snapshot history | Requested result sets, supplied write batches and final-result snapshots |
| Bundle-path handoff | Decoded objects queued between event workers/coordinator | One full result during encoding/decoding |
| Two workers, recycle after eight tasks in sweep | Concurrency and per-worker accumulation lifetime | Maximum memory of a single run |

These controls are not a hard RSS cap. Linux cgroup acceptance remains required
before claiming an enforced whole-machine budget; this macOS run cannot verify
that gate. Long histories and a high trade rate still require archive-aware
queries and bounded finalization, not just a language change.

Verification for this increment: 150 scenario/store/hook/repository/accounting
tests plus 31 subtests pass; 18 vector execution tests plus 88 subtests pass;
the event configuration/worker/risk suite passes with the eager-read change.
All 17 native tests and strict Clippy pass. The two new native tests cover
overflow rollback and unchanged storage for unrelated historical records.

## In-Memory Python Versus Rust (2026-09-21)

This comparison uses the **integrated vector engines**, both of which keep
trading state in memory. It is not a Python-event-versus-Rust-event comparison:
the native event broker still lacks Context/risk/result integration. No full
Rust event performance claim is justified by its isolated accounting tests.

Real EMA and RSI strategies, BTC/DOT 2h CSVs, dynamic sizing, fixed TP/SL and
cooldowns; three alternating fresh-process runs per backend/window/strategy
(24 runs). Python 3.12.14, macOS 26.6.2 arm64, NumPy 2.2.6, pandas 2.3.3,
PyArrow 24.0.0; locally rebuilt release Rust extension. Metrics stay Python
in both cases. All six exact execution hashes match within each workload,
excluding only generated IDs. No numeric tolerance is used.

| Workload | Python median (range), s | Rust median (range), s | Peak worker RSS Python/Rust, MiB |
| --- | ---: | ---: | ---: |
| EMA, 30 days | 0.238 (0.230-0.253) | 0.249 (0.248-0.252) | 319.6 / 322.2 |
| RSI, 30 days | 0.230 (0.228-0.252) | 0.258 (0.242-0.270) | 319.4 / 320.3 |
| EMA, 650 days | 1.601 (1.560-1.618) | 1.485 (1.469-1.495) | 376.9 / 378.2 |
| RSI, 650 days | 1.486 (1.478-1.570) | 1.520 (1.471-1.628) | 372.5 / 375.2 |

Execution includes signals, simulation, Python result construction, snapshots
and metrics; CSV preparation and process startup are outside this timer. EMA
650 days improves by 7.2%; other workloads show no improvement. This small
sample is not a confidence interval or evidence of a universal Rust speedup.
The long workloads produce 7,802 snapshots each (72 EMA trades, six RSI trades).

Harness end-to-end medians, including startup, transfer, save, merge and reload,
are 23.779/22.692 s for long EMA and 23.396/23.209 s for long RSI. Peak summed
process-tree RSS is 731.3/729.6 MiB and 726.7/721.5 MiB respectively. RSS is
sampled every 10 ms, includes interpreter/library overhead, double-counts shared
pages, and can miss short peaks. **No meaningful memory reduction from Rust is
established.** These are separate runs, not 50 concurrent algorithms.

Vector bundle roundtrips still change normalized metric representations
(`equity_curve`, yearly returns and best/worst trade/year fields). Record counts
and cross-engine execution hashes pass, but exact bundle fidelity remains open.
Do not interpret these measurements as passing that separate storage gate.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --backends python rust --strategies ema rsi --days 30 650 --repeats 3 \
  --output /tmp/iaf-in-memory-vector-stable-20260921.json
.venv/bin/python scripts/bench_backtest_streaming.py \
  --copy-reads --repeats 3 --output /tmp/iaf-copy-final-20260921.json
```

## Event Traversal Benchmark (2026-09-21)

Public `event_schedule_backend="python"|"rust"|"auto"` selects traversal only.
The Rust loop validates timestamps, advances through the materialized schedule,
checks Python signals, and invokes the unchanged Python tick boundary. Clock,
task/strategy/function ordering, snapshot batching, resource checks, error
propagation, worker isolation and result parity are preserved. Defaults and live
loops are unchanged. Missing/incompatible extensions are checked before a strict
run; auto fallback is allowed only before any tick executes.

Fresh baseline after the accounting corrections, 30-day EMA BTC/DOT, three
alternating fresh-process runs per backend, Python fill/metrics backends:

| Traversal | Median execution | Range |
| --- | ---: | ---: |
| Python | 9.882 s | 9.391-10.279 s |
| Rust | 10.039 s | 9.172-10.239 s |

All six runs matched exact result/bundle digests with five trades and 31
snapshots. Native invocation counters were one per native run and zero per
Python run. These overlapping ranges establish **no significant speedup**.
This is not comparable to the old accounting baseline.

```sh
.venv/bin/python scripts/bench_backtest_streaming.py \
  --backends event --strategies ema --days 30 --repeats 3 \
  --event-schedule-backends python rust \
  --output /tmp/iaf-event-schedule-20260921.json
```

A separate profiled pair counted **4,169 SQL statements inside 361 event ticks**
in each backend. `event_tick_sql_statements` instruments SQLAlchemy execution
inside `_run_iteration`; it excludes initialization, outer snapshot-batch
flushes and final result saving. Profiled timings are not speed measurements.
Add `--profile --repeats 1` to collect that diagnostic report.

The next meaningful performance gate is native authoritative state shared by
Context, order/fill accounting, risk, snapshots and results, with zero SQL inside
ticks and exact nonempty-trading/callback parity. Then repeat the benchmark and
the 50-algorithm acceptance sweep using fresh checkpoints, reporting execution,
RSS, serialization/transfer and saving separately. Traversal alone does not
complete native scheduling, broker integration or risk accounting, and does not
provide a memory bound.

## Goal

Run sweeps of approximately 50 algorithms on a 16 GB machine without per-bar
database transactions, unbounded historical-data retention, or large final-save
memory spikes. Keep the data boundary suitable for moving backtesting hot paths
to Rust incrementally.

Fifty algorithms in a sweep is not a promise of 50 concurrent Python processes.
Choose concurrency from measured peak memory, CPU capacity, and storage
throughput. If 50 simultaneous executions are required, establish that as a
separate benchmark target.

## Architectural Direction

Keep definition, evaluation, and execution responsibilities separate:

| Data | Examples | Proposed storage |
| --- | --- | --- |
| Immutable definitions | ConfluenceCard, future decision-tree definitions | Canonical versioned JSON, deduplicated by hash |
| Historical evidence | DecisionTrace records, snapshots, order/fill events | Typed, append-only, bounded chunks |
| Operational state | Current positions, pending orders, active risk state | Existing database initially |
| Run discovery | Status, scalar metrics, counts, artifact references | Small index and committed run manifest |

`ConfluenceCard` describes the decision model. `ConfluenceResult` is the runtime
evaluation result. `DecisionTrace` explains an evaluation and is not itself an
executable decision tree. Keep these distinct.

Extend the existing `BacktestStore` architecture rather than introducing a
separate persistence subsystem for each record type.

```text
Python configuration and orchestration
    -> Python engine initially / Rust hot paths later
    -> compact, byte-bounded record batches
    -> worker-owned immutable chunks
    -> committed run manifest

Coordinator receives manifest references and scalar metrics
    -> index updates and completion checkpoints

Analysis reads selected chunks lazily
    -> human-readable DecisionTrace reconstruction
    -> portable export when requested
```

## Existing Foundations and Gaps

Observed in the current code; not performance measurements:

- Worker/resource controls already exist: memory guards, recycling, incremental
  result checkpoints, and compact backtest indexes.
- Event backtests have isolated worker SQLite databases and a snapshot batching
  path. Do not assume every execution path uses the same batching settings.
- The event loop retains `signal_log` by default; optional signal recording
  writes bounded batches instead.
- Vector runs materialize snapshots, signals, and recorded values in results.
- Event workers return temporary bundle paths; vector workers still return
  decoded results. The event coordinator loads one bundle at a time.
- Bundle encoding materializes the whole MessagePack payload before compression.
  Decoding reads and decompresses the whole bundle even with `summary_only=True`;
  that option skips some subsequent decoding, not the initial full payload.
- Current bundle compression uses Zstandard level 19. Measure its cost before
  choosing a setting for high-throughput recording.
- `LocalTieredStore` already has SQL indexes, Parquet datasets, and shared OHLCV
  storage, but its historical datasets are derived from completed bundles.

Relevant code:

- [Event loop](../../investing_algorithm_framework/app/eventloop.py)
- [Event workers](../../investing_algorithm_framework/infrastructure/services/backtesting/event_workers.py)
- [Resource guards](../../investing_algorithm_framework/infrastructure/services/backtesting/vector_resources.py)
- [Bundle encoding and loading](../../investing_algorithm_framework/domain/backtesting/bundle.py)
- [BacktestStore protocol](../../investing_algorithm_framework/services/backtest_store/base.py)
- [Existing tiered store](../../investing_algorithm_framework/services/backtest_store/local_tiered_store.py)

## Phase 0: Finish the Naming Change

Completed 2026-09-14. `DecisionTrace` is canonical in the domain, runtime
recording, run reports, API schema, and SQL model attributes. This is a naming
and compatibility change only; historical recording remains non-streaming.

- [x] Inspect the current worktree and determine which interrupted edits applied.
- [x] Finish canonical `DecisionTrace` and `DecisionTraceEntry` types, module
  paths, exports, constants, annotations, and documentation.
- [x] Finish `Signal.with_decision_trace()` and
  `TradingStrategy.record_decision_trace()` across runtime callers.
- [x] Decide and document the legacy alias policy. Aliases alone do not preserve
  clients that rely on old serialized keys.
- [x] Verify run-report fields, API schema, signal/order metadata, database
  migration, and legacy deserialization behavior together.
- [x] Update examples and tests while preserving unrelated user edits.
- [x] Run domain, run-report, persistence, example, and lint checks.
- [x] Keep this naming change separate from the storage format transition.

### Compatibility Policy

- Canonical module: `domain.models.decision_trace`. The old `score_card`
  module, `ScoreCard`/`ScoreCardEntry` types, `with_score_card()`,
  `record_score_card()`, `last_score_cards`, and `RunReport.score_cards`
  remain compatibility aliases. No removal release is scheduled.
- `DECISION_TRACE_METADATA_KEY` is `"decision_trace"`;
  `SCORE_CARD_METADATA_KEY` retains its original `"score_card"` value.
- During the transition, output includes both metadata keys, both
  `decision_trace_version`/`score_card_version` fields, and both
  `decision_traces`/`score_cards` report lists. Consumers should use one naming
  family, not concatenate the alias lists. This deliberately duplicates wire
  data for compatibility; compact storage is deferred to later phases.
- Legacy signal/order metadata and run reports are normalized on read without
  mutating input payloads. Canonical keys take precedence when both exist;
  an explicit empty canonical list overrides a populated legacy list.
- `SQLRunReport.decision_traces_json` maps to the existing physical
  `score_cards_json` column. The old Python attribute remains a SQLAlchemy
  synonym. There is no destructive column rename, second history column, or
  bulk rewrite. The existing additive migration still upgrades older tables.
- Existing serialized artifacts remain readable through their domain readers;
  their storage format has not changed. New version fields are additive.

### Verification

- 83 focused domain, confluence, strategy, run-report, and API tests passed,
  including 79 subtests.
- 31 signal/order metadata and persistence tests passed, including loading
  legacy SQL rows, read-only normalization, and canonical updates.
- Migration tests cover tables without the history column, existing legacy
  records, repeated migration calls, and canonical-versus-legacy precedence.
- Both the confluence and decision-tracing examples run. The decision-tracing
  example calls the signal hook directly and prints the attached trace, without
  running orders. Its entry point and emitted/non-emitted decision hooks are
  covered by the focused trace suite (15 tests passed).
- Lint was checked. Existing unrelated whitespace/unused-import issues in
  user-edited examples and nearby files are not part of this naming migration.
  Editor import diagnostics also differ from the working Poetry environment.

See [the trace compatibility guide](../architecture/strategy/confluence_cards.md#decision-trace-compatibility)
for the public API and serialization contract.

## Phase 1: Establish Performance Baselines

- [ ] Choose representative event and vector workloads, including long windows,
  multiple symbols, frequent decisions, and a 50-algorithm sweep.
- [ ] Benchmark no historical recording, compact recording, and full diagnostic
  recording with identical data and strategy settings.
- [ ] Measure throughput, wall time, peak process-tree memory, allocation volume,
  serialized bytes, disk throughput, and database transaction counts.
- [x] Include worker startup, result handoff, compression, finalization, bundle
  merging, and analysis reads in measurements.
- [ ] Separate recording overhead from simulation, indicator computation, market
  data duplication, and database-backed trading-state costs.
- [ ] Define agreed throughput and recording-overhead acceptance targets before
  claiming the new architecture is faster.
- [ ] Establish a machine-wide memory reserve and a safe initial worker count.

Starting experiment only: four workers, about 12,000 MiB process-tree budget,
3,000 MiB available-memory reserve, and recycling after eight tasks. These are
not validated settings or hard memory guarantees. Increase concurrency only
after measuring representative peak memory.

### Measured Vector Snapshot Optimization

Implemented and measured 2026-09-19. The vector snapshot replay previously
scanned all trades on every bar. It now indexes trade opening/closing timestamps
once and visits only matching trades, preserving original trade-list order and
same-bar open-before-close processing. This changes lifecycle-event lookup from
O(bars * trades) to O(bars + trades), not the complexity of the whole engine.
Price lookups, position aggregation, trading logic and metrics are unchanged.

Reproduce from the repository root with
[the offline benchmark](../../scripts/bench_vector_snapshot_events.py):

```sh
poetry run python -m scripts.bench_vector_snapshot_events --bars 4000 --symbols 3 --repeats 3
poetry run python -m scripts.bench_vector_snapshot_events --bars 8000 --symbols 3 --repeats 3
```

Measured on macOS 26.6.2 arm64, Python 3.12.14, pandas 2.3.3. Synthetic hourly
OHLCV, three symbols, alternating long/short cycles, fixed sizing, one process.
Times are medians of three samples after one warmup per implementation; A/B
execution order alternates. Data generation and comparison happen outside the
timer. Timed scope includes the real vector engine, snapshots and metrics;
excludes app orchestration, data downloads, bundle I/O and worker handoff.

| Bars | Trades | Legacy Engine | Indexed Engine | Elapsed Reduction |
| --- | --- | --- | --- | --- |
| 4,000 | 3,000 | 2.065 s | 1.855 s | 10.2% |
| 8,000 | 6,000 | 5.083 s | 3.458 s | 32.0% |

Raw engine samples in seconds (legacy / indexed):

- 4,000 bars: `[2.065341, 2.045867, 2.286145]` /
  `[1.587429, 1.859044, 1.855498]`.
- 8,000 bars: `[5.082978, 5.038619, 5.383978]` /
  `[3.319712, 3.457522, 3.808254]`.

All compared snapshots, trades, orders, positions, signal events and metrics
matched exactly after excluding generated entity IDs. Regression coverage also
checks dynamic sizing, deposits, hedge mode, same-bar lifecycle ties and timezone
equivalence. Verification: 4 focused replay tests, 58 vector scenario tests and
31 event/vector scenario tests passed; 6 existing tests skipped. Touched files
pass lint. Editor pandas resolution differs from the working Poetry environment.

Trade-off: the index adds O(trades) references and timestamp buckets, released
before metric calculation. The isolated lookup benchmark measured 249,792 bytes
of peak Python allocation for 1,000 trades / 2,000 references, and 499,528 bytes
for 2,000 trades / 4,000 references. These are **index-only synthetic allocation
measurements**, not full-engine RSS or process-tree memory. Existing historical
collections still grow with run length. This is not streaming or a memory-bound
guarantee, and it does not validate the 50-algorithm/16 GB goal.

No Rust code was needed for this improvement. Phase 1 still needs representative
event/vector sweeps, recording-mode comparisons, process-tree memory, storage
and finalization measurements before its acceptance boxes can be checked.

### Measured Trading-Loop Input Preparation

Implemented 2026-09-19 as a Python optimization and preparatory boundary for a
future native execution loop. The vector engine now prepares positional price
and netting signal arrays once, instead of dispatching through pandas `.iloc`
for every price/signal read on every bar. NumPy-backed series use views where
possible; extension-backed series retain their extension arrays so nullable
scalar behavior is unchanged. There is no eager boolean/float coercion. Hedge
signal reads remain label-based to preserve their existing semantics; hedge
price reads use the prepared arrays. Trading-state mutations are unchanged.

Reproduce using the same offline benchmark:

```sh
poetry run python -m scripts.bench_vector_snapshot_events --loop-inputs --bars 4000 --symbols 3 --repeats 3
poetry run python -m scripts.bench_vector_snapshot_events --loop-inputs --bars 8000 --symbols 3 --repeats 3
```

On macOS 26.6.2 arm64, Python 3.12.14, pandas 2.3.3, three symbols, static
netting sizing, long/short cycles, one warmup and three alternating A/B repeats:

| Bars | Trades | pandas reads median | Array reads median | Elapsed reduction |
| --- | --- | --- | --- | --- |
| 4,000 | 3,000 | 1.614801 s | 1.505298 s | 6.8% |
| 8,000 | 6,000 | 3.215083 s | 2.946235 s | 8.4% |

Both arms include the prior lifecycle-event indexing improvement. These are
full vector-service timings including input preparation, simulation, snapshot
replay and metrics, excluding app orchestration, bundle I/O and worker startup.
Each run requires an identical normalized digest of snapshots, trades, orders,
positions, signals and metrics. Do not add these percentages to earlier results
or compare absolute times from separate sessions as a controlled experiment.

Focused tests cover static/dynamic sizing, shorts, hedge mode, deposits, empty
arrays and nullable scalar types; existing vector and event/vector scenario
suites pass. This is not a Rust trading loop, a streaming change or a measured
memory improvement. Rust execution still needs a typed mutable-state/event
contract preserving symbol order, same-bar exits, cooldowns, scaling, fees,
deposits and dynamic sizing, followed by batch-level parity tests. Avoid per-bar
FFI calls around Python trade objects. The current native confluence module is
unchanged by this optimization.

### Representative Profiling: 2026-09-19

Implemented [the offline profiling harness](../../scripts/bench_backtest_streaming.py).
It uses the repository's EMA crossover and RSI/EMA strategy fixtures, real
BTC/EUR and DOT/EUR CSVs, 600 warmup bars, 2-hour bars, EUR 10,000 initial
capital, dynamic sizing, 20% allocation per symbol, fixed 3% TP / 2% SL and a
three-bar sell-to-buy cooldown. Windows end on 2023-12-02. No network downloads
or writes to source fixtures are involved. RSI thresholds are 45/65 and EMAs
50/100 with four-bar crossover lookback. These are realistic indicator-based
fixtures, not claims about production strategies or investment performance.

Environment: macOS 26.6.2 arm64, Python 3.12.14, NumPy 2.2.6, pandas 2.3.3,
PyArrow 24.0.0, native netting-accounting-v5. All 36 vector runs had identical
normalized full-result digests between Python and Rust and after real Pipe IPC.
Generated entity IDs are excluded from these hashes. Three repeats alternate
backend order; each sample has a fresh spawned worker, not a warmed pool.

| Window | Strategy | Trades | Python execution median | Rust execution median | Python bundle-save median |
| --- | --- | --- | --- | --- | --- |
| 30 days | EMA | 5 | 0.243 s | 0.253 s | 0.095 s |
| 30 days | RSI/EMA | 1 | 0.233 s | 0.263 s | 0.104 s |
| 365 days | EMA | 42 | 0.979 s | 0.938 s | 0.884 s |
| 365 days | RSI/EMA | 4 | 0.945 s | 0.953 s | 0.710 s |
| 650 days | EMA | 72 | 1.611 s | 1.536 s | 1.625 s |
| 650 days | RSI/EMA | 6 | 1.516 s | 1.522 s | 1.837 s |

Execution includes indicators, input conversion, simulation, object
materialization and metrics. CSV preparation is timed separately. At 650 days,
EMA has 7,802 snapshots, 40 SL exits and 25 TP exits; RSI/EMA has five SL exits
and one TP exit. The native EMA improvement is 4.7%; RSI/EMA is effectively tied.
Do not apply the synthetic cycling speedup to all strategies.

For the 650-day Python EMA case: worker readiness (startup + preparation +
execution + digest + serialization) median 8.780 s; serialization 47.7 ms;
3,993,418 pickle bytes; Pipe receive 2.83 ms; unpickle 120.3 ms; save 1.625 s;
same-run bundle merge 1.739 s; full read 184.5 ms; bundle 141,303 bytes.
Readiness varied markedly across samples. The Pipe measurement is real IPC but
not the production pool scheduler. A same-run merge is not a multi-window sweep
merge. The normal bundle compressor remains unchanged at its existing setting.

The 650-day event EMA run uses the public Study API and DAILY snapshots:
72 trades, 651 snapshots, 40 SL and 25 TP callbacks observed. Two unprofiled
observations took 150.6 s and 173.7 s; the latter includes risk-hook counters.
The counter run serialized 445,521 bytes in 5.52 ms, received them in 0.214 ms,
unpickled in 8.06 ms, saved in 207 ms, merged in 142 ms and read in 113 ms.
Its bundle was 35,731 bytes. These are individual samples, not stable medians.
Different snapshot cadence, event fill behavior and sliding indicator windows
mean event/vector times are NOT an engine parity or speedup comparison.

Memory sampling sums RSS of the coordinator and its descendants with a requested
10 ms interval; actual intervals can be longer under load. Shared pages are
double-counted, short spikes may be missed, and digest validation itself creates
temporary objects. Vector process-tree peaks were 679-726 MiB across cases.
The unprofiled event peaks were 2.14 GiB and 2.11 GiB; worker-only peaks were
about 2,004 MiB and 1,814 MiB. These measurements do not validate four workers,
50 simultaneous processes, a machine-wide reserve, or a 50-algorithm sweep.

Separate cProfile runs were performed, not mixed into the timing medians.
Event profiles point to SQLAlchemy reads/execution, per-tick indicators and
data conversion; vector profiles retain substantial pandas indexing/materialization
work. Sampling-thread functions appear in the profile output and cumulative
times exceed measured wall time, so these profiles are diagnostic leads, NOT
trustworthy additive phase percentages. Allocation volume and DB transaction
counts still need dedicated instrumentation.

Bundle roundtrip caveat: event results matched the full normalized digest;
vector results preserved history counts and signal counts but did not match the
digest. The harness reports changed metric keys (including equity_curve,
yearly_returns and best/worst trade/year fields). Existing bundle representation
normalization needs a separate fidelity audit; this task does not change that
format or claim exact vector bundle roundtrips. Streaming Arrow chunks are
tested independently for exact schema/value roundtrips.

Reproduce from the repository root (JSON reports contain raw samples, fixture
SHA256s, per-phase sampled peaks, counts, digests and optional profile rows):

```sh
PYTHONHASHSEED=0 .venv/bin/python -m scripts.bench_backtest_streaming --days 30 365 650 --repeats 3 --output /tmp/iaf-vector.json
PYTHONHASHSEED=0 .venv/bin/python -m scripts.bench_backtest_streaming --days 650 --strategies ema --backends event --repeats 1 --output /tmp/iaf-event.json
PYTHONHASHSEED=0 .venv/bin/python -m scripts.bench_backtest_streaming --days 650 --strategies ema --backends python rust --repeats 1 --profile --output /tmp/iaf-profile.json
```

Still open in Phase 1: production worker-pool/sweep coverage, equal-strategy
none/compact/full engine recording comparisons (requires Phase 4), allocation
volume, transaction counts and agreed machine-wide acceptance thresholds.

## Phase 2: Define Language-Neutral Records

Contract and reference adapters implemented 2026-09-19. See the
[v1 record specification](backtest-records-v1.md) for exact schemas, hashing,
identity, provenance, compatibility and native-kernel candidates. These checks
mean the contract and opt-in adapters exist, not that engines stream these
records today. Emission, batching, manifests and retention remain later phases.

- [x] Specify versioned schemas shared by event, vector, and future Rust engines.
- [x] Define stable identifiers for algorithm, strategy, study/window, engine,
  run attempt, symbol, card definition, rule, and evaluation.
- [x] Specify timestamp units/timezone, numeric precision, null/missing values,
  enum encodings, ordering, and schema evolution.
- [x] Persist each canonical ConfluenceCard definition once by hash and reference
  it from evaluations. Define canonicalization and hashing rules precisely.
- [x] Record strategy/evaluator versions, parameters, market-data identity,
  indicator provenance, and execution settings. A definition hash alone is not
  sufficient for replay.
- [x] Define compact confluence evaluation fields: timestamp, symbol ID, card ID,
  score, qualification, matched-rule bits, requirement bits, and veto bits.
- [x] Include primary/expression outcomes where necessary for explanation; define
  how skipped, unavailable, and false evaluations differ.
- [x] Support arbitrary rule counts rather than assuming one fixed-width bitmask.
- [x] Preserve generic DecisionTrace entries that do not originate from a
  ConfluenceCard; do not force every trace into a confluence-only schema.
- [x] Specify optional indicator snapshots and irregular diagnostic details.
- [x] Link evaluation IDs to signals, risk rejections, orders, and fills.
- [x] Reconstruct readable names and explanations lazily from definitions and
  records, with tests against the existing trace representation.

Implementation scope: Arrow schemas and reference adapters, canonical definition
storage as an optional `BacktestStore` capability on `LocalTieredStore`, explicit
provenance validation, execution-link records and lazy trace reconstruction.
Existing algorithm/study ID adapters, automatic provenance capture and causal
link emission remain Phase 4 integration work. Phase 2 itself changes no hot
path; the separately implemented opt-in native evaluator is described in Phase 7.

Prefer typed columnar records and Arrow batches for the main data boundary,
Parquet for snapshots and regular historical records, and chunked MessagePack
with Zstandard only where irregular detail warrants it. Confirm these choices
with benchmarks. Arrow can avoid copies where layout and ownership permit; it
does not guarantee a zero-copy pipeline.

## Phase 3: Bounded Streaming Writer

- [x] Add an optional streaming-run writer capability to `BacktestStore`, keeping
  existing complete-object APIs available during migration.
- [x] Support begin, append batch, flush, commit, and abort semantics.
- [ ] Bound buffers by bytes and record count, including oversized-record policy,
  encoding temporaries, compression workspace, and queued batches.
- [x] Compare synchronous batch flushes with a bounded asynchronous writer.
  Add asynchronous complexity only when it improves measured throughput.
- [x] Apply backpressure when the writer cannot keep up; do not silently drop
  evidence or permit unbounded queues.
- [x] Write immutable chunks per worker/run attempt without concurrent append to
  one shared file or per-bar central SQLite transactions.
- [x] Define chunk sizing and compression settings through measurements; avoid
  both tiny-file proliferation and large-buffer memory spikes.
- [x] Define a manifest containing schema versions, references, record counts,
  time ranges, checksums, retention policy, and definition hashes.
- [x] Keep staging artifacts outside temporary directories that disappear before
  the coordinator can publish them.
- [ ] Publish durable artifacts and manifest before marking a run complete or
  advancing its checkpoint.
- [x] Define interrupted-run behavior, attempt isolation, idempotent retries,
  orphan cleanup, and checksum validation.
- [x] Distinguish durable trace chunks from resumable simulation state. Saving
  chunks alone does not enable mid-run simulation resume.
- [x] Specify local atomic publication and remote object-store publication
  separately; do not assume a remote atomic rename exists.

### Implemented Local Writer Contract

`SupportsStreamingRuns` is an optional protocol implemented by `LocalTieredStore`.
The existing `write`/`open` bundle API and its index are unchanged. Stream handles
are `run_id/attempt_id`, separate from bundle handles; they are not discoverable
as complete Backtest objects. Explicit schemas allow snapshot/order adapters
later, while Phase 2 evidence schemas work now.

```python
from investing_algorithm_framework.domain.backtesting.record_schemas import (
    record_batch, record_schema,
)
from investing_algorithm_framework.services.backtest_store import LocalTieredStore

store = LocalTieredStore("./durable-results")
with store.begin_run(
    "run-1", "attempt-1", {"generic_trace": record_schema("generic_trace")},
    retention="full", metadata={"engine": "vector", "window": "example"},
) as writer:
    writer.append_batch("generic_trace", record_batch("generic_trace", [{
        "evaluation_id": "ev-1", "attempt_id": "attempt-1", "sequence": 0,
        "timestamp_us": 1, "symbol_id": "BTC", "strategy_id": "ema",
        "trace_payload": b"{}",
    }]))
    handle = writer.commit()
for batch in store.iter_run_batches(handle, "generic_trace"):
    process(batch)
```

- Defaults: 8 MiB total retained Arrow buffers, 8,192 rows, 16 MiB encoded file,
  Zstandard level 3, no dictionary encoding, 64 KiB pages, 1,024-row encoder
  batches. Limits must be positive. Slices retaining an oversized parent buffer
  are rejected using `get_total_buffer_size`, even when logical `nbytes` is small.
- `append_batch` takes an already-built RecordBatch, checks exact schema metadata
  and required nullability, then synchronously writes one chunk. Oversized rows
  or batches are rejected before I/O, never silently split/dropped. Producers
  must construct small owned batches; this API cannot bound a caller's earlier
  allocation. Empty appends produce no files. There is no queue or retained
  history in the writer; a slow sink blocks the producer.
- The output adapter limits encoded file bytes. Encoding uses a single admitted
  batch plus Arrow/Zstandard workspace. Python/Arrow/native allocator overhead
  is measured, NOT hard-capped. The all-inclusive memory checkbox remains open;
  a process budget must include producer buffers, codec workspace and readers.
- Layout: `streams/<run>/<attempt>/chunks/000000000000.parquet`, disk-backed
  `chunks.jsonl`, and `manifest.json`. One producer owns each exclusive attempt.
  No shared append file between workers and no SQLite transactions per bar.
  The journal is mutable only before commit; chunks use exclusive creation.
- The bounded manifest includes format version, serialized schemas and their
  metadata, run/attempt IDs, counts, definition references, retention label,
  compression/limits and the journal SHA256. Journal entries hold relative chunk
  paths, record kind, counts, timestamp min/max (int64 timestamp_us), sizes and
  SHA256. It is streamed rather than accumulated during commit. Metadata plus
  schemas are capped at 64 KiB, 16 kinds and 256 definition references.
- `none` rejects appends. `compact` and `full` describe producer policy, not
  automatic filtering. Fine-grained retention semantics remain Phase 5 work.
  Referenced definitions must already exist and pass integrity validation.
- Chunks and journal are flushed/fsynced; `flush` syncs directories. Commit
  syncs a manifest staging file, publishes via an exclusive same-filesystem
  hard link, then fsyncs the directory before returning. The pending name is
  retained as a hard-link alias, not a second data copy. Readers require the
  committed name and validate index/definition checksums; iteration verifies
  every chunk checksum and its schema/counts before yielding it.
- Put the store root on durable local storage outside disposable worker temp
  directories. Normal local POSIX fsync/hard-link guarantees are assumed, not
  arbitrary network filesystem or hardware power-loss guarantees. Completion
  checkpoints must wait for successful commit; coordinator wiring is Phase 4.
- Commit is idempotent on the same successful writer. Reopening a committed
  handle reads its manifest; `begin_run` refuses any existing attempt. Failed
  append/flush/commit poisons the writer. Retry simulation with a NEW attempt ID.
  If publication succeeded but directory fsync failed, commit raises and the
  outcome is uncertain: inspect/verify the manifest, never mark it complete on
  that exception. Context exit aborts only unpublished attempts.
- `discard_run_attempt(handle, producer_stopped=True)` explicitly removes only
  unpublished attempts. Operators must first stop/join the owning producer.
  No unsafe age-based automatic cleanup. Published attempts cannot be aborted
  or discarded by this API. Crash tests use a separate process with `os._exit`;
  durable chunks alone do not permit resuming trading state mid-simulation.
- Remote stores need immutable object uploads followed by conditional manifest
  publication and visibility verification. Local hard links/rename semantics
  must not be assumed there; no remote writer is implemented.

### Writer Measurements

131,072 rows, three sequential samples per configuration. Compact records use
timestamp/value/symbol plus an empty payload; diagnostics add 256 seeded random
bytes per row. These synthetic records test the writer, not engine overhead.
The async experiment has one writer thread and at most two admitted batches;
it exists only in the benchmark. All rows were verified on readback.

| Record / batch rows | Zstd | Synchronous median | Async median | Stored size |
| --- | --- | --- | --- | --- |
| Compact / 1,024 | 3 | 1.663 s | 1.651 s | 1.25 MiB |
| Compact / 8,192 | 3 | 0.173 s | 0.164 s | 1.11 MiB |
| Compact / 8,192 | 9 | 0.256 s | 0.214 s | 1.11 MiB |
| Compact / 8,192 | 19 | 0.443 s | 0.475 s | 1.11 MiB |
| Diagnostic / 1,024 | 3 | 2.982 s | 2.940 s | 33.76 MiB |
| Diagnostic / 8,192 | 3 | 1.072 s | 1.145 s | 33.62 MiB |
| Diagnostic / 8,192 | 9 | 1.232 s | 1.168 s | 33.61 MiB |
| Diagnostic / 8,192 | 19 | 2.575 s | 2.287 s | 33.25 MiB |

Choose synchronous 8,192-row / level-3 defaults: async has no consistent benefit
at that setting; level 19 buys little size reduction at materially higher CPU
cost. Batch row limit is not a target that overrides the byte limit. Tiny
producer batches still create tiny files: engine adapters must batch upstream.

Fresh-process diagnostic scaling checks at this setting:

| Rows | Chunks | Write | Verified read | Peak admitted batch | Write RSS above baseline |
| --- | --- | --- | --- | --- | --- |
| 131,072 | 16 | 1.281 s | 0.082 s | 2,318,344 bytes | 20.3 MiB |
| 1,048,576 | 128 | 9.521 s | 0.631 s | 2,318,344 bytes | 20.8 MiB |

Stored bytes were 35,252,805 and 281,962,238 respectively. Peak read RSS above
baseline was 45.5 and 47.0 MiB. Codec allocator reuse affects these observations;
neither these two points nor sampled RSS establish a universal hard bound.

```sh
.venv/bin/python -m scripts.bench_backtest_streaming --writer --rows 131072 --repeats 3 --output /tmp/iaf-writer-matrix.json
.venv/bin/python -m scripts.bench_backtest_streaming --writer --rows 1048576 --repeats 1 --writer-batch-rows 8192 --writer-levels 3 --writer-modes sync --writer-retention diagnostic --output /tmp/iaf-writer-million.json
.venv/bin/python -m unittest tests.services.backtest_store.test_local_tiered_store -q
```

Verification: 28 tiered-store tests pass, including ten streaming tests for
admission limits, retained slice buffers, exact evidence roundtrips, slow-sink
backpressure, disk/manifest/fsync failures, killed producers, attempt isolation,
idempotent commit/abort, corruption detection and moved-store reads. Existing
bundle and definition tests remain green. Subsequent engine integration uses
this writer for optional signal reports, not snapshots or all trading history.

## Phase 4: Integrate Both Engines

- [x] Archive event snapshots and export disk-backed result histories without
  retaining every decoded result object.
- [x] Decode each metric input history once into compact scalar rows and share
  repeated batch calculations. This does not complete bounded metric memory.
- [x] Replace full-run event `signal_log` accumulation with a bounded recording
  sink for backtests, preserving required report semantics.
- [ ] Stream historical snapshots and decision records without altering mutable
  trading state or order/fill semantics.
- [ ] Generate vector trace records in batches from selected rows instead of
  constructing Python explanation objects per bar.
- [ ] Audit recorded values, completed orders/trades, schedules, and metric
  intermediates for other unbounded historical collections.
- [x] Event workers return saved bundle paths instead of decoded Backtest
  objects; the coordinator opens one returned bundle at a time. This bounds
  the handoff, not a worker's result creation or one bundle's decode size.
- [ ] Extend artifact-reference handoff and bounded result finalization across
  all execution paths, including vector workers.
- [ ] Keep coordinator index/checkpoint updates small and bounded.
- [ ] Avoid retaining both the full history and its newly flushed representation.
- [ ] Adapt metrics incrementally where exact; use bounded multi-pass reads where
  a metric needs history. Do not silently replace metrics with approximations.
- [ ] Preserve event/vector behavior and verify recording modes do not change
  signals, fills, portfolio values, or metrics.

## Phase 5: Retention and Query Semantics

- [ ] Design explicit policies: none, qualified, executed-trade-linked, sampled,
  and full diagnostic recording. Choose defaults through user needs and tests.
- [ ] Specify whether qualified means card-qualified or signal-emitted. Neither
  necessarily means executed after conflict, risk, and execution checks.
- [ ] Define deterministic sampling for rejected decisions and retain sampling
  metadata so analyses do not treat samples as complete history.
- [ ] For executed-trade-only retention, handle delayed fills without retaining
  pending trace objects indefinitely in memory.
- [ ] Keep required performance snapshots separate from optional diagnostic
  retention. Disabling traces must not disable metrics.
- [ ] Define identical policy meanings across event, vector, and future Rust
  execution; document any live/paper defaults separately.

## Phase 6: Lazy Analysis and Portable Artifacts

- [ ] Expose batch iterators and filters by run, symbol, time, definition, and
  evaluation outcome; require explicit full materialization.
- [x] Provide scalar backtest indexes for discovery/filtering and lazy full-run
  iteration.
- [ ] Extend index-backed queries to the new decision-record and retention
  dimensions without decoding histories.
- [ ] Make plots and trace inspection load only requested ranges/columns.
- [ ] Define whether immutable chunks plus manifest become canonical storage;
  treat this as an explicit format transition, not a transparent sidecar tweak.
- [ ] Keep existing `.obtf` artifacts readable and provide a migration/export
  path with bounded memory.
- [ ] Ensure export includes referenced chunks and definitions without loading
  the complete history into RAM.
- [ ] Verify moves/uploads preserve reference resolution; avoid worker-local
  absolute paths in portable manifests.
- [ ] Avoid generating redundant full bundles and sidecars on every hot-path
  write. Consider compaction/export as a separate operation.

## Phase 7: Rust Hot Paths

### Implemented: Optional Confluence Batch Kernel

Implemented 2026-09-19 in [native/confluence](../../native/confluence/README.md),
with a separate Maturin/PyO3 package. The main package still uses Poetry and
requires neither Rust nor the extension for its default behavior.

```sh
poetry run python -m pip install ./native/confluence
poetry run python -m unittest tests.domain.models.test_confluence_native -q
poetry run python -m scripts.bench_confluence_native --rows 4000 --rules 32 --repeats 5
poetry run python -m scripts.bench_confluence_native --rows 100000 --rules 32 --repeats 5
```

```python
result = card.evaluate_series(frame, backend="rust")
fallback_result = card.evaluate_series(frame, backend="auto")
```

Python remains the default. `rust` requires the extension and supported inputs;
`auto` explicitly opts into native execution with fallback to the existing pandas
evaluator for an unavailable extension or unsupported definition/dtype. This does
not extend the pandas evaluator's support for custom Python expressions.
Missing columns and runtime kernel failures are not silently swallowed.

The kernel compiles built-in expressions into immutable indexed expression trees,
with a process-local 128-entry definition cache. It evaluates float64/nullable
Float64 columns, comparisons, crossings, compound logic, groups, requirements,
vetoes and scores, returning the existing score/available/qualified DataFrame.
It uses one native call per frame, owns its copied numeric buffers, releases the
GIL during computation, and runs on one native thread. The semantics version is
`confluence-vector-v1`, not scalar short-circuit semantics. NaNs are unavailable;
infinities in columns remain valid. Float constants roundtrip exactly through
JSON; integer columns are rejected rather than rounded. Each call starts fresh
crossing history; callers splitting frames must prepend the prior row and discard
its result. See the native README for full eligibility and ownership details.

Final release-wheel measurements on macOS 26.6.2 arm64, Python 3.12.14, pandas
2.3.3, NumPy 2.2.6, Cargo 1.87.0. Synthetic four-column workload with 32 scoring
rules, nested logic, crossings and missing values; one warmup per backend,
five alternating-order repeats, exact result parity checked outside timing:

| Rows | pandas median | Rust median | pandas / Rust | First Rust call |
| --- | --- | --- | --- | --- |
| 4,000 | 18.883 ms | 2.064 ms | 9.15x | 15.803 ms |
| 100,000 | 37.679 ms | 38.140 ms | 0.99x | 52.357 ms |

Timing includes definition serialization/cache lookup, input copies, FFI,
computation, output copies and DataFrame construction. First-call timing also
includes extension import and compilation. It excludes initial framework import,
data/indicator preparation, engine execution, recording and bundle I/O. The larger
batch is effectively tied and slightly slower in this run; there is no universal
native speedup or full-backtest speedup claim. Peak RSS and concurrent execution
have not been benchmarked. Buffers grow with the caller's frame size.

Verification: 57 Python confluence/native/record tests and two Rust unit tests
pass; strict Clippy, Python lint and focused editor checks pass. Tests include
all operators, timeframes/references, nullable values, infinities, exact float
thresholds, grouped score order, large rule counts, empty frames, overlap at chunk
boundaries, fallback and invalid inputs. The wheel was built/tested locally on
macOS arm64/Python 3.12; cross-platform wheels and CI coverage remain pending.

### Implemented: Experimental Rust Netting Core

Implemented 2026-09-19 in [netting.rs](../../native/confluence/src/netting.rs).
`VectorBacktestService.run(..., execution_backend="rust")` performs the complete
bar/symbol decision traversal and numeric snapshot replay in one GIL-releasing
native call for eligible NETTING runs. It computes fills, fees, slippage,
static/dynamic built-in sizing, deposits, position accounting and gains. Flips,
symbol/portfolio cooldowns and fixed TP/SL now run natively as well. Python
materializes orders, trades and snapshots from computed records and packed f64
buffers, and retains final position construction and metrics. Neither Python
accounting helpers nor the Python per-bar snapshot loop are replayed.

Public `BacktestRunConfiguration.execution_backend` forwards this selection
through app runs and vector workers; optimizer-specific coverage remains open.
`execution_backend="auto"` falls back for unsupported inputs or an
unavailable extension; strict `rust` raises. Native runtime errors propagate.
Python stays the default. Unsupported features are hedge mode, scaling,
trailing risk rules, custom sizing/cost/risk models and
simultaneous long/short entries. Inputs require finite positive float64 prices
and nonnullable boolean signals. These restrictions prevent silently changing
trading behavior. Dynamic sizing requires CPython 3.12+ float summation semantics
(tested on 3.12.14). Vector TP/SL's existing full-close semantics are preserved.

The shared optional wheel exports `NETTING_SEMANTICS_VERSION=netting-accounting-v5`;
the original `static-netting-v1` entry point remains available. It copies input
arrays into Rust-owned buffers and materializes all events and snapshots. It is
neither a bounded streaming writer nor an Arrow zero-copy path.
See the [native README](../../native/confluence/README.md#experimental-vector-execution-loop)
for install/use, the event contract, ownership, unsupported modes and remaining
packaging/provenance limits.

Full-vector-service benchmark, same machine/toolchain as the confluence kernel,
three symbols, one warmup and five alternating repeats with the v5
cooldown/TP/SL-capable core, exact normalized result parity
on every run:

| Bars | Trades | Python median | Rust median | Elapsed reduction |
| --- | --- | --- | --- | --- |
| 4,000 | 3,000 | 1.474052 s | 1.270264 s | 13.8% |
| 8,000 | 6,000 | 2.798443 s | 2.472607 s | 11.6% |

These timings cover static zero-cost cycling signals without active risk rules.
For real strategies with active risk and saving, see the Phase 1 profiling above.
Conversion,
event reconstruction, snapshots and metrics are included; app orchestration,
pool startup and bundle I/O are excluded. No universal speedup or memory-bound
claim follows. Reproduce with:

```sh
poetry run python -m scripts.bench_vector_snapshot_events --native-loop --bars 4000 --symbols 3 --repeats 3
poetry run python -m scripts.bench_vector_snapshot_events --native-loop --bars 8000 --symbols 3 --repeats 3
```

Verification: 132 Python tests (74 focused execution/confluence/record and 58
vector scenarios), seven Rust tests, Python lint and strict Clippy pass. Native
parity includes randomized signal outcomes, shared-capital contention, exits
before entries, zero-sized/fee-exhausted entries, costs, sizing, deposits, open
positions, flips, cooldown scope/boundaries and fixed TP/SL. Combined randomized
cases and two deterministic Python hash seeds preserve exact full-result parity.
NumPy scalar types at the result boundary must be preserved for exact downstream
metric summation, even when scalar values compare equal. Strict rejection and
fallback are tested separately. Existing service call sites remain compatible.

### Implemented: Optional Event Fill Selection

Implemented 2026-09-20 in [event.rs](../../native/confluence/src/event.rs).
`BacktestRunConfiguration(event_fill_backend="rust")` selects the native
OHLCV trigger/fill search in sequential and spawned event runs. The default is
`python`; `auto` falls back for missing/incompatible native support or unsupported
inputs. The environment option is `IAF_BACKTEST_EVENT_FILL_BACKEND`. It is
independent of vector `execution_backend` and the low-level `metrics_backend`.
Strict native availability is checked before the event loop, even when
`continue_on_error=True`; use `False` to propagate unsupported per-order inputs.

The `event-fill-v1` kernel covers MARKET, LIMIT, STOP and STOP_LIMIT orders,
including BUY, SELL, SHORT and COVER. It preserves input row order, the inclusive
updated-at boundary, stop trigger persistence, and the existing already-triggered
STOP behavior. Python applies each decision immediately through `_apply_fill`;
custom blotters, partial fills, fees, slippage, portfolio reconciliation and
trade hooks keep their existing implementation and order. Trade price updates
and take-profit-before-stop-loss evaluation also remain Python.

Each call copies one order's candle timestamp/low/high arrays to Rust and releases
the GIL for selection. This is **not a Rust event engine**, an in-memory broker,
multi-order batching, shared market buffers, or bounded full-history storage.
Polars datetime columns (ms/us/ns) and compatible Python datetime order updates
are supported; prices must be finite Python float/int values, with integer
magnitudes at most 2**53. Nullable/nonfinite prices, Decimal values, missing
required columns and unsupported types fall back in `auto` or raise in `rust`.
Required columns are Datetime/Open/Low/High; Volume is optional. Native runtime
errors are not silently retried after side effects.

### Native Event Core: Remaining Stages

The requested native event core is still open. Moving the outer loop alone
would retain per-tick Python/SQL costs. The next implementation should establish
one authoritative state owner rather than duplicate mutable SQL and Rust state:

- [x] Pure native OHLCV fill decisions, sequential Python application, public
  selector, spawned-worker forwarding, exact parity and benchmark baseline.
- [ ] Native in-memory order/position/cash store behind backtest-only service
  adapters. Preserve Context queries and callback-visible state; keep live
  trading repositories unchanged. Start with an explicitly validated NETTING
  subset, not all event features at once.
- [ ] Native reservation, fill reconciliation, fees, deposits, cancellation,
  close/flip accounting and active risk state. Preserve mutation/hook ordering,
  partial fills and TP/SL tie behavior. Preflight unsupported models before
  starting; do not silently switch engines after native state has advanced.
- [ ] Native scheduler advancement over shared immutable market arrays, yielding
  to Python only at strategy/task/hook boundaries. Callback queries must see
  committed state; callback orders must affect the next eligible evaluation.
  Preserve multiple-strategy order, clocks and snapshot cadence.
- [ ] Bounded record emission and finalization from native state, followed by
  isolated per-algorithm concurrency and whole-machine memory acceptance.

Acceptance requires exact Python/native orders, trades, cash, positions,
snapshots and metrics, plus ordered callback observations; exercise stop-limit
trigger-only ticks, partial fills, cancellation, deposits, custom-model rejection,
shared-capital contention and restart boundaries. Benchmark this separately from
the fill selector before offering a general event execution backend.

### Remaining Work and Gates

- [ ] Keep Python responsible for configuration, orchestration, and supported
  user-defined strategy hooks while moving eligible computation incrementally.
- [ ] Compile declarative confluence expressions once into indexed instructions:
  indicator columns, stable rule IDs, constants, and boolean operations.
- [x] Define supported expressions and an explicit Python fallback for custom
  expressions. Do not imply arbitrary Python strategies compile automatically.
- [ ] In hot loops, evaluate against numeric arrays and append compact records
  to reusable buffers; avoid per-bar SQL, JSON, strings, and Python objects.
- [x] Cross Python/Rust boundaries in batches, not callbacks per rule or bar.
- [x] Specify Arrow/FFI ownership, lifetimes, error handling, and where copies
  remain necessary.
- [ ] Release the GIL for eligible native execution and benchmark a bounded Rust
  thread pool sharing immutable market arrays rather than duplicated processes.
- [ ] Keep per-algorithm mutable trading state isolated and preserve deterministic
  results independent of worker scheduling.
- [ ] Match Python semantics for crossings, missing/non-finite values, boolean
  composition, scoring, requirements, vetoes, and trace ordering.
- [ ] Benchmark Rust compute-only and compute-plus-recording paths separately.

Checked items apply to the optional native subsets only. Compilation is cached,
but stable rule IDs, per-rule bitsets and compact record emission are not native
yet. GIL release is implemented; a bounded thread pool is not. Arrow zero-copy
FFI, native trace ordering, full-engine integration, packaging matrix and the
machine-wide memory gates are still open.

## Event Sweep Verification (2026-09-20)

The 50-algorithm event sweep now passes the unchanged exact saved-result
digest comparison between baseline and signal recording. The failing run
exposed two SQL ordering gaps: trade-order relationships had no explicit
chronological order, and order queries did not resolve equal timestamps using
stable business fields. Simultaneous BTC/DOT sell fills could consequently
execute in either order and change cash by approximately 1e-12, propagating
into metrics. Both producer query paths now specify ordering; no float
tolerance or digest normalization was introduced.

Verified with two workers, BTC/DOT EMA strategies, 30 days, daily event
snapshots, and Python 3.12.14 on macOS arm64:

| Mode | Execute/transfer/save | Resume | Peak process-tree RSS | Stored bytes |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 258.194 s | 2.186 s | 1,438,629,888 | 402,180 |
| Signal recording | 252.957 s | 2.217 s | 1,515,307,008 | 552,530 |

Each mode produced 250 trades and 1,550 snapshots. Recording persisted 18,050
signal reports. Both resume checks passed without changing the saved index;
the recording resume also left the 50 committed manifests unchanged.
These are single measurements, not evidence of a speedup. The report is
`/tmp/iaf-sweep-event-fixed-20260920.json`; the earlier failing artifacts remain
available separately. Focused repository/evaluator tests passed (15 tests),
as did the broader repository, event recording, and trade-service regression
run (56 tests).

This closes the observed event parity failure only. No hard memory cap was
enabled on macOS; full-history boundedness and the agreed machine-wide reserve
remain unverified. The event loop remains Python.

## Acceptance Gates

See the measured native-metrics comparison and worker-handoff status below;
neither closes the full-history or hard-memory gates.

- [ ] A representative 50-algorithm sweep completes within the agreed 16 GB
  machine budget and reserve, including finalization and result handoff.
- [ ] Historical-record buffers and queues remain bounded as run length grows;
  remaining memory growth is identified separately from historical recording.
- [ ] A deliberately slow writer triggers backpressure without unbounded growth.
- [ ] Worker crashes, disk-full errors, and interrupted commits never publish
  incomplete runs as successful or silently lose required evidence.
- [ ] Restart/retry does not duplicate published evaluations or checkpoints.
- [ ] New and legacy artifacts pass persistence and reconstruction tests.
- [ ] Retention does not affect trading outcomes or required metrics.
- [ ] Python/Rust parity is tested before replacing a production hot path.
- [ ] Benchmarks report actual overhead and throughput, not assumed gains from
  batching, Rust, compression, or asynchronous I/O.

## Event Worker Handoff (2026-09-20)

Parallel event workers now save temporary `.obtf` bundles and return paths over
IPC. The coordinator loads one result, performs the existing save/checkpoint
work, then removes that temporary file. A pool-lifetime temporary directory also
cleans unconsumed files after ordinary Python failures. Abrupt process termination
can leave orphan directories; these are not resumable checkpoints. Bundle
encoding/decoding still materializes full histories, and vector handoff is
unchanged. This is a transfer-memory change, not bounded engine execution.

The repeated 50-algorithm/30-day/two-worker event sweep took 265.626 s baseline
and 261.534 s with signal recording, versus 258.194 s and 252.957 s before the
handoff change. Peak sampled process-tree RSS was 1,399,816,192 and 1,502,068,736
bytes respectively. These single samples are about 3% slower with slightly lower
RSS, not a speedup. All 100 before/after saved-result digests matched exactly;
both resumes passed. Each mode produced 250 trades and 1,550 snapshots, with
18,050 external reports in recording mode. Raw report:
`/tmp/iaf-sweep-event-handoff-20260920.json`.

## Shared Native Risk Metrics (2026-09-20)

The new `drawdown-v1` kernel moves raw drawdown series, maximum percentage and
absolute drawdown, duration, TWR equity compounding, and TWR drawdown calculations
into Rust. One call releases the GIL and computes both curves; Python still sorts
and validates snapshots and reconstructs timestamp/value pairs. Other metrics,
including daily loss, ratios and their internal drawdown calls, remain Python.
The kernel uses whole-history vectors, not streaming or zero-copy buffers.

`create_backtest_metrics(run, risk_free_rate, metrics_backend="rust")` and the
low-level vector/event services accept `python` (default), strict `rust`, or
`auto` (fallback for missing/incompatible native support or unsupported inputs).
This selector is independent of vector `execution_backend` and is **not yet
forwarded by the public app/sweep configuration**. Installing the wheel alone
does not change execution. The event trading loop remains Python.

Supported input values are finite Python floats, NumPy float64, and Python ints
within +/-2**52. Larger integers, other numeric types, nonfinite values, mixed
timezone objects, non-`datetime` timestamps and nonfinite TWR growth are rejected
in strict mode. Stable timestamp sorting and Python's duration convention are
retained: duration starts at the first underwater observation, not the peak.
Non-positive equity is skipped for percentage drawdown, but included in absolute
loss and duration. Native absolute-loss peak/trough indices preserve Python's
scalar type. No fast-math or relaxed result tolerance is used.

### Python/Rust Benchmark

Fresh spawned process per sample, three repeats in alternating backend order,
`PYTHONHASHSEED=0`, macOS 26.6.2 arm64, Python 3.12.14, NumPy 2.2.6,
pandas 2.3.3, PyArrow 24.0.0 and Cargo 1.87.0. BTC/EUR + DOT/EUR EMA strategy,
2-hour bars, 600-bar warmup, initial EUR 10,000, dynamic sizing, 3% TP, 2% SL,
and three-bar sell-triggered cooldown. No profiler enabled.

| Workload | Execution backend | Risk metrics | Median execution | Execution range | Median all-metrics phase |
| --- | --- | --- | ---: | ---: | ---: |
| Vector, 650 days | Python | Python | 1.551 s | 1.526-1.573 s | 1.280 s |
| Vector, 650 days | Python | Rust | 1.559 s | 1.558-1.623 s | 1.291 s |
| Vector, 650 days | Rust netting | Python | 1.503 s | 1.486-1.566 s | 1.293 s |
| Vector, 650 days | Rust netting | Rust | 1.465 s | 1.445-1.486 s | 1.282 s |
| Event, 30 days | Python | Python | 9.852 s | 8.607-10.158 s | 0.062 s |
| Event, 30 days | Python | Rust | 9.086 s | 8.975-9.353 s | 0.071 s |

Vector results contain 72 trades and 7,802 snapshots; event results contain five
trades and 31 daily snapshots. Compare backends **within each workload**, not the
different event/vector windows. All 18 full-result execution digests matched
within their engine. The harness asserts that metric calculation was invoked;
it overrides metric creation only inside the benchmark worker, allowing the
event app path to exercise the selector before public API forwarding exists.

The combined vector median is about 5.5% lower, but sample ranges overlap and
the new metric port alone shows no clear gain. Event medians differ by about
7.8%, yet the metric phase became slower and execution ranges overlap strongly:
this is not evidence of a Rust event speedup. Rust coverage increased; a material
end-to-end improvement from this port is **not demonstrated**.

Vector execution timing includes strategy/engine/metric work but excludes process
startup, input preparation, subsequent Pipe transfer and bundle saving. Event
execution timing wraps the public app call, including its internal data
preparation and persistence; only the harness's additional transfer/save phases
are excluded. Those phases remain separately reported; the harness Pipe test is
not the production event path-handoff measurement. Existing vector bundle metric
normalization is separately reported and is not covered by the execution digest
parity claim. Raw local reports:
`/tmp/iaf-native-risk-vector-20260920.json` and
`/tmp/iaf-native-risk-event-20260920.json`.

```sh
.venv/bin/python -m pip install --force-reinstall ./native/confluence
PYTHONHASHSEED=0 .venv/bin/python -m scripts.bench_backtest_streaming --days 650 --strategies ema --backends python rust --metrics-backends python rust --repeats 3 --output /tmp/iaf-native-risk-vector.json
PYTHONHASHSEED=0 .venv/bin/python -m scripts.bench_backtest_streaming --days 30 --strategies ema --backends event --metrics-backends python rust --repeats 3 --output /tmp/iaf-native-risk-event.json
.venv/bin/python -m pytest tests/services/metrics tests/infrastructure/services/backtesting/test_vector_snapshot_events.py -q
cargo test --manifest-path native/confluence/Cargo.toml
cargo clippy --manifest-path native/confluence/Cargo.toml --all-targets -- -D warnings
```

Verification: 521 Python tests plus 112 subtests and eight Rust tests passed;
strict Clippy passed. Coverage includes exact raw/TWR parity, deposits, empty,
flat, unrecovered and recovered curves, non-positive equity, Python/NumPy scalar
types, malformed buffers, oversized integers, nonfinite inputs, backend selection
and missing-extension fallback. Python remains the default. Full-machine memory
acceptance, long event-window repetitions and cross-platform wheels remain open.

## Event Fill Benchmark (2026-09-20)

The same BTC/DOT EMA fixture and toolchain as the risk-metrics benchmark above,
30 days, three fresh-process samples per backend in alternating order. Metrics
remain Python in both cases. These measurements use the public event selector,
not a benchmark-only backend override. Five trades, 31 daily snapshots and four
stop-loss hooks were observed in every run. Native selection was actually called
nine times per native run. All six full-result digests matched exactly, and all
six event bundle round trips preserved the digest.

| Event execution | Median | Range | Native selector calls/run |
| --- | ---: | ---: | ---: |
| Python event engine, Python fill selection | 10.009 s | 9.213-10.049 s | 0 |
| Python event engine, Rust fill selection | 9.460 s | 9.439-10.950 s | 9 |

The median difference is about 5.5%, with heavily overlapping ranges and only
nine selector calls across the workload. **No event speedup is established.**
Per-order input validation/copies and Python/SQL work remain; there is no memory
reduction claim. Execution is timed around the public event app call, which
includes its internal preparation and persistence. Process startup, the harness's
subsequent Pipe transfer, and additional bundle save/read measurements are separate.
The harness Pipe transfer is not the production event-worker handoff.

For vector Python/Rust comparisons, see the 650-day real-strategy table in
[Shared Native Risk Metrics](#shared-native-risk-metrics-2026-09-20) and the
4,000/8,000-bar execution benchmark in Phase 7. Compare backends within one
engine/workload, not event and vector timings with different windows/cadences.

Reproduce after rebuilding the optional wheel:

```sh
.venv/bin/python -m pip install --force-reinstall ./native/confluence
.venv/bin/python -m scripts.bench_backtest_streaming --days 30 --strategies ema --backends event --event-fill-backends python rust --repeats 3 --output /tmp/iaf-native-event-fills.json
.venv/bin/python -m pytest tests/domain/test_backtest_run_configuration.py tests/services/test_backtest_trade_order_evaluator.py tests/app/backtesting/test_backtest_memory_options.py -q
.venv/bin/python -m pytest tests/infrastructure/services/backtesting/test_vector_snapshot_events.py -q
cargo test --manifest-path native/confluence/Cargo.toml
cargo clippy --manifest-path native/confluence/Cargo.toml --all-targets -- -D warnings
```

Local report: `/tmp/iaf-native-event-fills-20260920.json`. Tests cover 64 combinations
of order type, side, prior trigger and volume; microsecond/nanosecond fixtures;
trigger-only persistence; unsupported-input and missing-extension fallback;
custom partial/zero fills and no-fill cases; exact spawned-worker result parity
and checkpoint resume. The final combined configuration/evaluator/worker/vector
regression run passed 52 tests and 215 subtests. Scoped Python lint, strict Clippy
and ten native unit tests pass; both event-service call sites remain compatible.
The measured
platform is macOS arm64/Python 3.12; long-window repetitions, platform wheels,
and Linux hard-memory acceptance remain open.

## Scope Boundaries

- Keep operational trading-state storage unchanged in the first iteration.
- Do not add a remote service dependency for local backtesting.
- Do not implement temporal confluence expressions, correlation caps, sizing
  policy, or a general strategy compiler as part of the storage change.
- Do not promise 50 concurrent Python workers or a specific speedup without
  representative measurements.
- Definition persistence, complete replay provenance, and trace retention are
  separate requirements; confirm each rather than conflating them.
