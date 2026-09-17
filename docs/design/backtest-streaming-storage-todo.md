# Backtest Streaming Storage and Rust Readiness

Status: Phase 0 naming migration implemented and verified; streaming storage
and Rust phases remain proposed, not implemented or benchmarked.
Last updated: 2026-09-14.

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
- The event loop appends signal reports to `signal_log` for the entire run.
- Vector runs materialize snapshots, signals, and recorded values in results.
- Event workers return full result objects to the coordinator.
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
- [ ] Include worker startup, result handoff, compression, finalization, bundle
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

## Phase 2: Define Language-Neutral Records

- [ ] Specify versioned schemas shared by event, vector, and future Rust engines.
- [ ] Define stable identifiers for algorithm, strategy, study/window, engine,
  run attempt, symbol, card definition, rule, and evaluation.
- [ ] Specify timestamp units/timezone, numeric precision, null/missing values,
  enum encodings, ordering, and schema evolution.
- [ ] Persist each canonical ConfluenceCard definition once by hash and reference
  it from evaluations. Define canonicalization and hashing rules precisely.
- [ ] Record strategy/evaluator versions, parameters, market-data identity,
  indicator provenance, and execution settings. A definition hash alone is not
  sufficient for replay.
- [ ] Define compact confluence evaluation fields: timestamp, symbol ID, card ID,
  score, qualification, matched-rule bits, requirement bits, and veto bits.
- [ ] Include primary/expression outcomes where necessary for explanation; define
  how skipped, unavailable, and false evaluations differ.
- [ ] Support arbitrary rule counts rather than assuming one fixed-width bitmask.
- [ ] Preserve generic DecisionTrace entries that do not originate from a
  ConfluenceCard; do not force every trace into a confluence-only schema.
- [ ] Specify optional indicator snapshots and irregular diagnostic details.
- [ ] Link evaluation IDs to signals, risk rejections, orders, and fills.
- [ ] Reconstruct readable names and explanations lazily from definitions and
  records, with tests against the existing trace representation.

Prefer typed columnar records and Arrow batches for the main data boundary,
Parquet for snapshots and regular historical records, and chunked MessagePack
with Zstandard only where irregular detail warrants it. Confirm these choices
with benchmarks. Arrow can avoid copies where layout and ownership permit; it
does not guarantee a zero-copy pipeline.

## Phase 3: Bounded Streaming Writer

- [ ] Add an optional streaming-run writer capability to `BacktestStore`, keeping
  existing complete-object APIs available during migration.
- [ ] Support begin, append batch, flush, commit, and abort semantics.
- [ ] Bound buffers by bytes and record count, including oversized-record policy,
  encoding temporaries, compression workspace, and queued batches.
- [ ] Compare synchronous batch flushes with a bounded asynchronous writer.
  Add asynchronous complexity only when it improves measured throughput.
- [ ] Apply backpressure when the writer cannot keep up; do not silently drop
  evidence or permit unbounded queues.
- [ ] Write immutable chunks per worker/run attempt without concurrent append to
  one shared file or per-bar central SQLite transactions.
- [ ] Define chunk sizing and compression settings through measurements; avoid
  both tiny-file proliferation and large-buffer memory spikes.
- [ ] Define a manifest containing schema versions, references, record counts,
  time ranges, checksums, retention policy, and definition hashes.
- [ ] Keep staging artifacts outside temporary directories that disappear before
  the coordinator can publish them.
- [ ] Publish durable artifacts and manifest before marking a run complete or
  advancing its checkpoint.
- [ ] Define interrupted-run behavior, attempt isolation, idempotent retries,
  orphan cleanup, and checksum validation.
- [ ] Distinguish durable trace chunks from resumable simulation state. Saving
  chunks alone does not enable mid-run simulation resume.
- [ ] Specify local atomic publication and remote object-store publication
  separately; do not assume a remote atomic rename exists.

## Phase 4: Integrate Both Engines

- [ ] Replace full-run event `signal_log` accumulation with a bounded recording
  sink for backtests, preserving required report semantics.
- [ ] Stream historical snapshots and decision records without altering mutable
  trading state or order/fill semantics.
- [ ] Generate vector trace records in batches from selected rows instead of
  constructing Python explanation objects per bar.
- [ ] Audit recorded values, completed orders/trades, schedules, and metric
  intermediates for other unbounded historical collections.
- [ ] Make workers return artifact references and scalar summaries instead of
  full decoded Backtest objects.
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
- [ ] Serve scalar discovery/ranking from indexes without decoding histories.
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

- [ ] Keep Python responsible for configuration, orchestration, and supported
  user-defined strategy hooks while moving eligible computation incrementally.
- [ ] Compile declarative confluence expressions once into indexed instructions:
  indicator columns, stable rule IDs, constants, and boolean operations.
- [ ] Define supported expressions and an explicit Python fallback for custom
  expressions. Do not imply arbitrary Python strategies compile automatically.
- [ ] In hot loops, evaluate against numeric arrays and append compact records
  to reusable buffers; avoid per-bar SQL, JSON, strings, and Python objects.
- [ ] Cross Python/Rust boundaries in batches, not callbacks per rule or bar.
- [ ] Specify Arrow/FFI ownership, lifetimes, error handling, and where copies
  remain necessary.
- [ ] Release the GIL for eligible native execution and benchmark a bounded Rust
  thread pool sharing immutable market arrays rather than duplicated processes.
- [ ] Keep per-algorithm mutable trading state isolated and preserve deterministic
  results independent of worker scheduling.
- [ ] Match Python semantics for crossings, missing/non-finite values, boolean
  composition, scoring, requirements, vetoes, and trace ordering.
- [ ] Benchmark Rust compute-only and compute-plus-recording paths separately.

## Acceptance Gates

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

## Scope Boundaries

- Keep operational trading-state storage unchanged in the first iteration.
- Do not add a remote service dependency for local backtesting.
- Do not implement temporal confluence expressions, correlation caps, sizing
  policy, or a general strategy compiler as part of the storage change.
- Do not promise 50 concurrent Python workers or a specific speedup without
  representative measurements.
- Definition persistence, complete replay provenance, and trace retention are
  separate requirements; confirm each rather than conflating them.
