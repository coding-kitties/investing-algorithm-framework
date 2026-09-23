# Backtest Evidence Records v1

Status: implemented contract and reference adapters, 2026-09-19. Engine sinks,
bounded chunk writers, committed manifests, retention policies and Rust kernels
are not implemented by this phase. A separate opt-in Rust batch evaluator is
now available; see the progress notes below. Existing bundles and trading behavior are
unchanged. These are internal storage APIs, imported from
`domain.backtesting.records` and `domain.backtesting.record_schemas`.

## Scope and Physical Schemas

[record_schemas.py](../../investing_algorithm_framework/domain/backtesting/record_schemas.py)
is the executable Arrow schema specification. `record_schema(kind)` returns its
fields, nullability and metadata; `record_batch(kind, rows)` constructs one
caller-bounded batch. It does not chunk an unbounded iterator. No pandas objects,
Python classes, pickles, native addresses or engine-specific enums cross this
boundary. Rust may construct the same Arrow arrays directly.

Every batch has `iaf.record_kind` and `iaf.record_version=1` metadata. A future
manifest must repeat these values per artifact. Timestamps are signed int64
microseconds since 1970-01-01T00:00:00Z, not nanoseconds or floating-point seconds.
They remain int64 columns in Arrow/Parquet. Naive datetimes are rejected at the
Python adapter; aware timestamps are converted to UTC using integer arithmetic.

| Kind | Fields |
| --- | --- |
| `confluence_evaluation` | Common identity; `card_id: utf8`; nullable `score: f64`, `qualified: bool`; `primary_outcome: u8`; five binary bit vectors; `group_scores: list<element: nullable f64>`; nullable `detail_id: utf8` |
| `generic_trace` | Common identity; `trace_payload: binary` |
| `diagnostic` | `detail_id: utf8`, `evaluation_id: utf8`, `payload: binary` |
| `execution_link` | `attempt_id: utf8`, `sequence: i64`, `timestamp_us: i64`, `evaluation_id: utf8`, `entity_kind: utf8`, `entity_id: utf8`; nullable `parent_kind`, `parent_id`, `detail_id` (utf8) |
| `run_context` | `attempt_id`, `algorithm_id`, `study_id`, `window_id`, `engine_id`, `provenance_id` (non-null utf8) |

Common identity fields, all required: `evaluation_id: utf8`, `attempt_id: utf8`,
`sequence: i64`, `timestamp_us: i64`, `symbol_id: utf8`, `strategy_id: utf8`.
The strategy reference is necessary even when several strategies use one card.
`generic_trace` and `confluence_evaluation` are alternative representations for
an evaluation, not two records to concatenate for the same evaluation ID.

`record_batch` checks shape, required values, Arrow types and link enums.
Definition-aware confluence validation belongs to
`ConfluenceEvaluation.from_record`. It also verifies bit lengths/padding,
identity and consistency between redundant primary/status fields. These are
format checks, not proof that a producer computed correct trading outcomes.

Arrow batches are the shared boundary; regular historical chunks should use
Parquet. Diagnostic binary payloads currently contain canonical JSON described
below. Chunked MessagePack/Zstandard remains a future physical encoding option,
not a second competing logical schema. Compression and batch sizes need Phase 1
measurements. Arrow does not make ownership or copies disappear automatically.

## Identity and Ordering

Immutable descriptor IDs use `content_id(kind, descriptor)`. The result is
`<kind>:sha256:<64 lowercase hex digits>`. Descriptor fields are explicit, not
inferred from display names, object addresses, SQL primary keys or file paths.
Existing framework IDs may be retained in an `origin` field, never assumed
globally unique without their namespace.

| Kind / identity | Descriptor or construction rule |
| --- | --- |
| `strategy` | `{version: 1, origin: {namespace, key}, code_digest, parameters}`; identifies a configured implementation, not just its class name |
| `algorithm` | `{version: 1, origin: {namespace, key}, strategies: [strategy_id, ...], configuration}`; strategy order is significant |
| `study` | `{version: 1, origin: {namespace, key}, configuration}`; excludes execution attempts and wall-clock creation time |
| `window` | `{version: 1, study_id, start_us, end_us, interval, warmup_start_us}`; `interval` explicitly states boundary inclusion (`closed`, `left_closed`, `right_closed`, `open`), rather than silently changing existing engine boundaries |
| `engine` | `{version: 1, name, implementation_version, semantics_version, build_digest}`; event, vector and Rust builds can share record schemas without claiming identical semantics |
| Attempt | Allocate `attempt:<lowercase UUIDv4>` once at attempt start. Retransmitting writes keeps it; restarting simulation allocates another. It is not a deterministic logical-run ID |
| `symbol` | `{version: 1, venue, instrument, base, quote, instrument_type}`; use canonical venue instrument identity, not an ambiguous ticker alone |
| `card` | Complete `ConfluenceCard.to_dict()` including definition version, names, order, expressions and thresholds |
| Rule | `<card_id>#<definition path>`; paths such as `requirements/0`, `primary/rules/0`, `primary`, `vetoes/0`, `secondary/0/rules/0`, `scoring/0` |
| Evaluation | `content_id("evaluation", [attempt_id, sequence])` |
| `provenance` | Full validated provenance document, excluding attempt ID, so identical replay inputs can be reused across attempts |

Descriptor adapters for existing algorithm/study objects remain engine
integration work; callers currently supply IDs. Hashing does not establish that
the supplied source/data digest is truthful or available for replay.

Evaluation sequences are nonnegative int64, allocated monotonically across
both trace kinds, all symbols and all strategies within one attempt. Allocate
before retention filtering, so gaps are legal. Engine scheduling must supply
deterministic tie ordering; never derive order from worker completion times or
unordered sets. Rows are emitted in sequence order. Timestamps can tie; sequence
is the authoritative event order. Cross-attempt sequence comparison is undefined.
Link records have a separate per-attempt sequence namespace. Diagnostic records
are looked up by ID, not ordered as evaluations.

Retries cannot be deduplicated by evaluation ID across *different* attempts.
The later manifest/coordinator must select the successful attempt for a logical
run. Persisting evidence is not resumable simulation state.

## Canonicalization and Hashes

This is the explicitly named **IAF typed canonical JSON v1** profile, not RFC
8785 or ordinary `json.dumps(sort_keys=True)`. It uses a tagged JSON tree to
avoid differences between language-specific decimal float printers and to
preserve integer/float/bool distinctions. Every node is encoded as:

| Input | Canonical node |
| --- | --- |
| null | `["null"]` |
| boolean | `["bool", true]` or `["bool", false]` |
| signed int64 | `["int", "<base-10 integer>"]`, no leading zeros/plus, zero is `"0"` |
| finite IEEE-754 binary64 | `["float", "<16 lowercase hex digits of big-endian bits>"]` |
| Unicode string | `["str", "value"]` |
| ordered array | `["list", [node, ...]]` |
| string-keyed object | `["map", [["key", node], ...]]` sorted by Unicode scalar value of keys |

Serialize the tagged tree as compact ASCII JSON, no spaces or terminal newline.
String escaping: escape quote and backslash; use `\b`, `\f`, `\n`, `\r`, `\t`
for those controls; other U+0000..U+001F and all codepoints >= U+007F use lowercase
`\uXXXX`. Supplementary codepoints use a UTF-16 surrogate pair. Do not escape
`/`. Reject lone surrogates. Do not normalize Unicode. Arrays preserve order;
Python tuples normalize to arrays. Reject non-string map keys, nonfinite
numbers and values outside the profile. Map order is not semantic; snapshot
entry order therefore uses an array of pairs, not a map.

Hash exactly ASCII `iaf-records:1:<kind>\n` followed by the canonical bytes,
using SHA-256. `kind` is a nonempty ASCII identifier containing only `a-z` and
`_`. The prefix/version provides domain separation. All bytes of definitions,
including descriptive names, affect their IDs. Int `1`, float `1.0`, `true`,
`0.0` and `-0.0` are deliberately distinct; no implicit coercion/rounding is
allowed. Producers must agree on these types. A canonical decoder re-encodes
and compares bytes to reject duplicate keys, alternative spellings and padding.

Golden example for `{"b": 1.0, "a": 1}`:

```json
["map",[["a",["int","1"]],["b",["float","3ff0000000000000"]]]]
```

`CardDefinition` validates a complete supported card and stores immutable bytes.
Custom Python `Expression` subclasses without a serializable built-in definition
are not silently compiled or hashed; use a generic trace and explicit code
provenance instead.

### Definition Persistence

`SupportsRecordDefinitions` is an optional capability alongside `BacktestStore`.
`LocalTieredStore.put_definition(kind, payload)` validates canonical bytes,
validates card/provenance documents when applicable, and returns their ID.
Definitions are stored at `definitions/<kind>/<digest>.json` under the existing
store root. They contain the typed canonical tree, not ordinary card JSON.
`get_definition(id)` verifies canonical encoding and hash on each read.

Publication uses a same-directory temporary file, file fsync, then a
no-replacement hard link. Concurrent writers of identical content converge on
one immutable file. Existing corrupt content is an error, not overwritten.
POSIX publication also fsyncs directories. The filesystem must support hard
links; unsupported filesystems fail explicitly. Windows directory durability
is not guaranteed by this implementation. This is not a remote-store protocol.

References contain IDs, not absolute worker paths, so moving the store preserves
resolution. Ordinary bundle deletion does not garbage-collect shared definitions.
Garbage collection, run manifests, exporting referenced definitions, cleanup of
crash-left temporary files and definition-aware `copy_from` are deferred. A
successful definition write alone does not publish a successful run.

## Evaluation Semantics

Outcome codes are `0=false`, `1=true`, `2=skipped`, `3=unavailable`.
False means a predicate was evaluated with usable inputs and did not match.
Skipped means it was not evaluated (for example, expression short-circuiting).
Unavailable means evaluation was attempted but required inputs/history were
unusable. Neither skipped nor unavailable is false. Unknown codes are rejected.

Card-level slots follow the existing scalar trace order exactly:

1. Requirements in definition order.
2. Primary scoring rules, if the primary is a rule group.
3. One primary result, including an expression-only primary.
4. Vetoes in definition order.
5. Each secondary group's scoring rules in group/rule order.
6. Additional scoring rules in definition order.

Duplicate rule names are legal because paths, not labels, identify slots.
Primary/secondary scoring-rule categories remain `score`, matching today's
`DecisionTrace`. Group labels and score types come from the definition.

The five binary vectors are:

- `matched_rule_bits`: TRUE for scoring slots only, in slot order.
- `requirement_bits`: TRUE for requirement slots only.
- `veto_bits`: TRUE for veto slots only (true means rejection, not approval).
- `evaluated_bits`: all slots; 0=skipped, 1=evaluated/attempted.
- `available_bits`: all slots; 1=boolean outcome, 0=skipped/unavailable.

Bit `index` is `(bytes[index // 8] >> (index % 8)) & 1`. Length is exactly
`ceil(slot_count/8)` for the relevant category. Unused high bits in the final
byte must be zero; empty vectors are empty bytes. There is no 64-rule ceiling.
Available implies evaluated. Match bits must be zero when unavailable/skipped.
The redundant `primary_outcome` must agree with the two status masks.

The Python reference object exposes byte-per-slot `outcomes` for construction;
`to_record` packs them into this wire layout. It is not the native hot-loop
representation and does not claim production recording performance.

`score` and all group scores are finite binary64, not currency fixed-point.
Group scores are stored in primary-group-then-secondary order. Keep recorded
totals rather than reconstructing sums in a new floating-point reduction order.
Binary64's limits apply; exact money/fill quantities would need a separate
decimal contract and are not introduced here. Qualification means card-qualified,
not signal-emitted, risk-approved, order-created or filled.

If any card-level slot is skipped/unavailable, `score` and `qualified` are null.
Completed groups may retain scores; incomplete groups use null. Empty groups do
not invent a score. For a complete row, totals and group scores are present.
An absent optional field means not recorded; null is explicit unknown/not
applicable, never zero. Null slots remain visibly skipped/unavailable in traces.

Internal expression children are not extra card-level slots. When a compound
root evaluated successfully but some child was short-circuited, record the root
boolean and, if requested, the child SKIPPED outcome in diagnostics. Do not
re-evaluate children for explanation: that could execute user code or change
which missing-input errors occur.

## Generic Traces and Diagnostics

`encode_trace` preserves arbitrary generic `DecisionTrace` entries, their order,
summary, unit, description and group. It stores only `decision_trace_version`;
`decode_trace` restores the existing representation including compatibility
aliases. A card is not required. Nonfinite scalar values accepted by some old
Python callers are rejected at this strict JSON boundary; the producer must
explicitly represent missing values, not silently substitute zero.

`diagnostic_record` produces a canonical payload with `version=1`,
`evaluation_id`, `indicator_snapshot` (ordered `[name, scalar]` pairs),
`expression_outcomes` (ordered `[path, outcome-code]` pairs), and `details`
(profile-compatible irregular data, or null). Indicator scalar types are
preserved, including string, bool, int and explicit null. Include provenance
names in the snapshot; avoid repeating indicator implementations per bar.

Expression paths are definition paths: begin at a rule's `/expression` (or
`primary/expression`), then append `/expressions/<index>` for compound children
or `/expression` for `Not`. Paths must be unique in one diagnostic document.
Readers resolving expressions validate paths against the referenced definition;
the payload helper validates codes/uniqueness, not that resolution. Details can
carry missing-data reasons, risk rejection context or unsupported custom logic.
Do not assume diagnostics are present merely because a definition is present.

The detail ID is `content_id("detail", document)` and binds the payload to the
evaluation. `iter_decision_traces` reads one row/definition and optional detail
at a time, validates references, and renders through the existing trace API.
It never evaluates indicators/expressions and holds no history cache. Missing
referenced definitions/details are errors, not silently omitted explanations.
Detailed expression outcomes remain accessible in the diagnostic document;
they do not add new entries to the legacy flat trace representation.

## Replay Provenance

A definition hash proves definition identity, not replayability. The provenance
document requires `version`, algorithm/study/window/engine IDs, plus:

- `strategies`: strategy ID, implementation version, code digest, parameters,
  evaluator semantics version, and referenced card IDs.
- `market_data`: symbol ID, provider, immutable content digest, coverage
  `start_us`/`end_us`, timeframe, and adjustment settings. A mutable URL or cache
  filename alone is insufficient.
- `indicators`: name, implementation, version, parameters, input identities,
  warmup settings, temporal alignment, and missing-value policy. An empty list
  explicitly means no indicators; a missing list is invalid.
- `execution`: fees, slippage, sizing, fill timing, risk, conflict settings,
  randomness seed and recording policy, including sampling configuration.
- `environment`: framework version, dependency versions, and platform.

Unknown information is explicit null and makes replay completeness unproven;
validation ensures structure, not source availability or deterministic external
hooks. Producers must not claim full replay when dependencies, data or code are
missing. Provenance belongs to the run, not every evaluation. Changes to fees,
warmup, data or evaluator version change provenance even if card identity stays
the same. Do not serialize secrets in parameters or execution settings.

## Execution Causality

Execution links connect one evaluation to one entity per row. `entity_kind` is
the string enum `signal`, `risk_rejection`, `order`, or `fill`. `entity_id` is an
attempt-scoped stable producer identifier; database IDs require an explicit
namespace when imported. Parent kind/ID are either both null or both present.
A fill normally refers to its parent order; partial fills have distinct IDs.
Multiple evaluations can link to one order and one evaluation to multiple fills.
No link is inferred from timestamps alone. No link means no recorded causal
edge, not evidence that an order did or did not execute.

Rows may arrive after the evaluation chunk; readers resolve across committed
attempt artifacts. Linking schemas are implemented; generating links inside
signals/risk/orders/fills is Phase 4 work. No current execution metadata is
changed. Link retention and deferred fills must not force pending trace objects
to remain in memory indefinitely.

## Evolution and Compatibility

Schema version is per record kind; card and DecisionTrace versions are separate.
Changes to meaning, numeric units, enum encodings, positional rule layout or
canonicalization require a new major record version. Definition changes produce
new hashes; never reinterpret old evaluation bits against a new card. Unknown
major versions must be rejected for reconstruction/replay, not guessed.

Additive optional columns can remain v1. New readers default absent optional
columns to null before constructing reference objects; old readers project
known columns. The v1 writer uses the exact known schema and rejects extra keys.
`from_record` ignores unknown columns but requires the complete v1 projection.
Required fields and enum codes cannot be added under the additive rule.
Applications explicitly normalize older projections; these adapters do not
provide a general future-version migration registry.

Legacy `.obtf`, SQL reports, signal metadata and their duplicate trace aliases
remain unchanged. This phase does not make definition sidecars a substitute for
legacy bundles or switch canonical run storage.

## Verification and Rust Candidates

[Record tests](../../tests/domain/test_backtest_records.py) cover canonical byte
vectors, strict values, exact timestamps, arbitrary bit counts, definition and
trace roundtrips, grouped scores, duplicate names, skipped/unavailable states,
generic traces, diagnostics, lazy reads, provenance and Arrow/Parquet schema
preservation. Existing confluence tests remain the behavior oracle.
[Store tests](../../tests/services/backtest_store/test_local_tiered_store.py)
cover deduplication, concurrent publication, relocation and corruption.

A **separately packaged opt-in native kernel** now implements numeric confluence
batch evaluation. See the [Phase 7 progress notes](backtest-streaming-storage-todo.md#phase-7-rust-hot-paths)
for measured timings, parity checks and limits, and the [native README](../../native/confluence/README.md)
for installation. It does not emit these evidence records or change the default
engine. No speedup follows from the record contract alone. Remaining candidate
ranking below is based on code structure, not a profile:

| Candidate | Boundary and prerequisite |
| --- | --- |
| Built-in confluence batch expressions | Implemented opt-in for float64/Float64 columns: cached compilation, copied numeric arrays, score/availability/qualification outputs, GIL release and exact pandas parity tests. Callers supply crossing overlap when chunking. Stable rule IDs, per-rule bitsets, evidence-record emission and Arrow zero-copy remain pending. Oracle: [confluence_frame.py](../../investing_algorithm_framework/domain/models/confluence_frame.py) |
| Vector portfolio snapshot replay | [Vector engine](../../investing_algorithm_framework/infrastructure/services/backtesting/vector_backtest_service.py) now indexes lifecycle events instead of scanning all trades per timestamp; the Python optimization is measured in the [Phase 1 progress notes](backtest-streaming-storage-todo.md#measured-vector-snapshot-optimization). Price-history slicing and position aggregation remain candidates. Profile those before a native port; preserve deposits, short liabilities and partial fills |
| Vector execution and fixed TP/SL | A strict opt-in static, zero-cost netting loop now executes bars in Rust and emits ordered events for Python order/trade reconstruction; see the [native README](../../native/confluence/README.md#experimental-vector-execution-loop). TP/SL, hedge, dynamic sizing, scaling, cooldowns, costs and deposits remain Python-only; `_evaluate_tp_sl` has take-profit-winning ties that future ports must preserve |
| Compression and serialization | Arrow, Parquet, MessagePack and Zstandard already have native implementations. Measure conversion/allocation and compression settings before adding another native wrapper |

The existing [Rust benchmark](../../examples/rust_vs_python_benchmark/README.md)
is a standalone Cargo program, not a PyO3 framework backend. Its documented
indicator initialization, parameter sampling, metric coverage and bundle-I/O
differences prevent treating its timing as a production parity result.

Scalar confluence short-circuits `AllOf`/`AnyOf`; vector evaluation visits every
child and propagates unavailable inputs. Scalar comparisons also do not apply
one universal nonfinite-input policy. Do not erase these differences in Rust.
Declare a semantics version and test nulls/NaNs/infinities, first-row crossings,
equal-threshold crossings, empty batches, group reduction order and chunk
boundary history. Custom Python expressions/hooks retain a Python fallback.

Before default native dispatch or broader engine integration: profile representative compute/recording
workloads separately, agree on the target, prove Python/native parity, specify
Arrow ownership/lifetimes and allowed copies, release the GIL only around native
work, cap threads against the machine-wide memory budget, and benchmark the full
Python/native handoff. Keep a tested optional fallback and packaging matrix.