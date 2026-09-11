# Pluggable backtest optimization: API and design

**Status:** Base contracts, local orchestration and durable resume implemented.
Concrete optimizers, external-library adapters and distributed execution are
not included.

Both `App.run_backtest` and `App.run_backtests` accept `optimization=`.
Supply your own `StrategyOptimizer` implementation. Omitting optimization
preserves the ordinary backtest API and execution path.

## 1. Decision summary

Add an optimization coordinator above the existing backtest engines. The
coordinator proposes strategies, evaluates batches using the existing runner,
and reports scalar observations to a pluggable optimizer.

Keep three responsibilities separate:

| Object | Responsibility |
| --- | --- |
| `Study` | Universe, engine, capital, cost assumptions and evaluation windows |
| `BacktestRunConfiguration` | Checkpoints, persistence, workers, progress and resource controls |
| `OptimizationConfiguration` | Candidate source, optimizer, objective and search budget |

`app.run_backtests(...)` continues to return a `BacktestIndex`, including when
optimization is enabled. Search history and optimizer state are persisted
separately in `optimization_state.json`, which contains the trial observations
and optimizer snapshot. There is not yet a dedicated report-reader API.

Random, grid and CryStAl search are potential plugins, not bundled
implementations or engine dependencies. No optimizer is assumed to
improve out-of-sample performance merely because it improves training fitness.

### Why add an optimizer?

An optimizer answers **"Which parameter combinations should we evaluate
next?"** It automates candidate generation and, for adaptive algorithms,
uses earlier scores to guide the next proposals.

For a small parameter space, manually generating all combinations and running
a fixed sweep is often sufficient. The benefit grows when the combinations
become too numerous to evaluate exhaustively. For example, four parameters
with 20 possible values each produce 160,000 combinations. Over five windows,
that is 800,000 candidate/window evaluations before pruning or cache reuse.
A search budget of 200 unique candidates instead admits at most 1,000 such
evaluations if all candidates complete all five windows without retries.
It explores only part of the space and may miss the best combination.

Benefits include:

- **Controlled search cost:** spend a declared evaluation budget instead of
  having to run an exhaustive grid.
- **Automated exploration:** generate valid parameter combinations rather
  than hand-maintaining hundreds of strategy variants.
- **Feedback-driven search:** adaptive plugins can concentrate evaluations
  in promising regions while retaining exploration elsewhere. Random and
  grid search do not adapt to scores, but still fit the same execution API.
- **Repeatable experiments:** record the parameter space, objective, seed,
  trial history and selected parameters.
- **Shared execution infrastructure:** reuse checkpointed evaluations and
  bounded workers without each optimizer rebuilding the backtest integration.

These are search and engineering benefits, not guarantees of a global optimum
or better live trading. A faster search can also overfit historical data more
efficiently. Compare search methods under equal budgets and assess selected
parameters on untouched out-of-sample windows.

### Optimizer versus filter function

A filter answers **"Which of the results we already have should we keep?"**
It selects a subset of existing algorithms; it does not create new parameter
combinations or move the search toward unexplored combinations.

| Mechanism | Main decision | Generates candidates? | Uses results to choose new candidates? | Can save future evaluation work? |
| --- | --- | --- | --- | --- |
| Fixed strategy sweep | Evaluate the supplied strategy list | No; caller supplies them | No | Only through checkpoints or additional pruning |
| Optimizer | Choose candidates to evaluate | In parameter-space mode | Depends on the plugin | Yes, by limiting and directing the search |
| Window metrics filter | Choose which evaluated algorithms continue to later windows | No | No | Yes, by skipping later windows for rejected algorithms |
| Final metrics filter | Choose which completed results appear in the returned index | No | No | No; the evaluations have already happened |
| Objective function | Assign a score to an evaluated candidate | No | Not itself; the optimizer consumes the score | Not by itself |

For example, suppose a fixed sweep contains 500 SMA strategies:

1. A window filter can reject strategies exceeding a drawdown threshold after
   the first window. This saves their remaining window evaluations, but the
   first-window evaluations have already been paid for.
2. A final filter can return only the ten highest-ranked completed strategies.
   It does not make the preceding backtests cheaper.
3. An optimizer can begin with a smaller candidate batch and, depending on the
   plugin, propose new fast/slow-period combinations based on their scores.
   Those combinations need not have appeared in an initial fixed list.

An optimizer does not replace filters. The proposed combined flow is:

```text
optimizer proposes candidates
    -> backtest evaluates windows
    -> optional window filter prunes candidates
    -> objective scores complete candidates
    -> optimizer receives observations and proposes the next batch
    -> final filter selects returned results after the search
```

Keep the roles separate: constraints reject invalid parameters before
execution, filters select existing results, objectives measure performance,
and optimizers decide where to search. If a window filter prunes a candidate,
report it as partially evaluated rather than giving its partial score the
same meaning as a complete multi-window evaluation. Population-relative
filters such as "keep the top ten" also require care when optimizer batches
have different sizes or members; see Section 8.

## 2. Relevant v9 contracts

- Public backtest results are disk-backed `BacktestIndex` objects.
- A window metrics callback sees results through the current window and
  selects algorithms allowed to continue. A final metrics callback selects
  the returned results after evaluation.
- Window summaries must be current regardless of filtering. Updating them is
  not a user-selectable execution mode.
- Checkpoints contain `{window_id: [algorithm_id, ...]}`. The current window
  key is the start/end date pair, not the display name of a window.
- Checkpoint matching uses only that window key and algorithm ID. It does
  not inspect strategy code, compare parameter manifests, or include the
  study/engine/universe in the lookup key.

Relevant implementation surfaces:

- [Public app orchestration](../../investing_algorithm_framework/app/app.py)
- [Backtest runner and checkpoints](../../investing_algorithm_framework/infrastructure/services/backtesting/backtest_service.py)
- [Window-scoped scalar summaries and filters](../../investing_algorithm_framework/infrastructure/services/backtesting/vector_session_index.py)
- [Algorithm ID generation](../../investing_algorithm_framework/domain/algorithm_id.py)
- [Index row contract](../../investing_algorithm_framework/domain/backtesting/backtest_index_row.py)

## 3. Goals and non-goals

### Goals

1. Allow interchangeable search methods without rewriting strategy evaluation.
2. Reuse both engines, bounded worker scheduling and existing result storage.
3. Evaluate batches rather than launching a complete backtest session for
   every scalar fitness call.
4. Avoid recomputing identical resolved candidate/window pairs.
5. Resume both the expensive evaluations and the search state reliably.
6. Preserve scalar-only index semantics and expose trial outcomes clearly.
7. Make constraints, objective direction, evaluation budgets and randomness
   explicit.

### Non-goals for the first release

- Distributed optimizer coordination or multiple writers to one search.
- Multi-objective Pareto optimization.
- Automatic selection of trading objectives or train/test boundaries.
- Automatic code-change detection through backtest checkpoints.
- Treating optimization as evidence of profitability.
- Importing CryStAl, scipy or a Bayesian search library into the core runtime.

## 4. Public usage

### Existing algorithms

Search a finite collection without declaring parameters or a factory:

```python
from investing_algorithm_framework import OptimizationConfiguration

results = app.run_backtests(
    algorithms=my_algorithms,
    study=training_study,
    run_configuration=run_configuration,
    optimization=OptimizationConfiguration(
        search_id="finite-search",
        optimizer=my_optimizer,
        objective=objective,
        direction="maximize",
        max_evaluations=100,
        max_proposals=1_000,
        proposal_batch_size=16,
    ),
)
```

`my_optimizer` is a user-supplied plugin supporting `"finite"` search spaces.
Each candidate needs a unique, nonempty algorithm ID. `strategies=` and the
singular input arguments are supported too. A finite optimizer proposes one
of the supplied IDs; it cannot create candidates outside that collection.

### Generated strategies

Use a factory and numeric parameters instead. `my_parameter_optimizer` below
is a user-supplied plugin supporting `"parameters"` search spaces:

```python
def build_strategy(params, algorithm_id):
    return TunableSMAStrategy(
        algorithm_id=algorithm_id,
        fast_period=params["fast_period"],
        slow_period=params["slow_period"],
        stop_loss_percentage=params["stop_loss_percentage"],
    )


def valid_parameters(params):
    return params["fast_period"] < params["slow_period"]


def objective(index):
    pooled = index.df.loc[index.df["universe_key"].isna()]
    if len(pooled) != 1:
        raise ValueError("Expected one pooled candidate row")
    return float(pooled["summary.sharpe_ratio"].iloc[0])


results = app.run_backtests(
    study=training_study,
    run_configuration=BacktestRunConfiguration(
        backtest_storage_directory="./searches/sma-001",
        n_workers=8,
        memory_budget_mb=16_384,
        min_available_memory_mb=4_096,
    ),
    optimization=OptimizationConfiguration(
        search_id="sma-001",
        strategy_factory=build_strategy,
        parameters=[
            IntegerParameter("fast_period", lower=3, upper=30),
            IntegerParameter("slow_period", lower=10, upper=120),
            FloatParameter(
                "stop_loss_percentage", lower=1.0, upper=10.0, step=0.5,
            ),
        ],
        constraints=[valid_parameters],
        optimizer=my_parameter_optimizer,
        objective=objective,
        direction="maximize",
        max_evaluations=200,
        max_proposals=2_000,
        proposal_batch_size=16,
    ),
)
```

Only factory mode is mutually exclusive with a preconstructed `strategies=`
or `algorithms=` collection. The strategy factory is responsible for producing
one independently evaluated candidate strategy per resolved parameter set.
Combined multi-strategy algorithms can be considered later.

Omitting `optimization=` retains the ordinary fixed-strategy sweep behavior.
The runner should resolve its persistent directory once for the entire search,
not create a new directory for every generation.

### Result contract

Return the session-scoped index of fully evaluated, successful candidates,
subject to the explicit final metrics filter. Do not return only the winner
by default: preserving the evaluated alternatives matters for comparison.

Keep proposed trial fields such as objective score and failure status in a
dedicated trial table. Do not silently extend the frozen canonical index row
schema. A report reader can join trials to index rows by algorithm ID and
evaluation namespace.

An empty successful-results index is valid when no candidate finishes
successfully, but the report must say that there is **no valid best trial**.
It must not manufacture a best parameter vector.

## 5. Parameter space and candidate identity

### Authoritative resolution

The framework, not each optimizer, owns parameter resolution. It validates:

- Unique names and exact coordinate count.
- Finite bounds with lower <= upper.
- Valid integer ranges and positive steps when discretization is requested.
- Valid categorical choices and positive bounds for logarithmic parameters.
- Finite proposed values.
- Cross-parameter constraints after resolution.

For stepped parameters, define the legal grid as `lower + k * step` for
nonnegative integer `k` while the value remains <= upper. An upper bound is
not automatically on the grid. Do not snap above upper and then clip to an
off-grid upper bound.

Use separate integer and floating parameter specifications rather than
relying on an independent `round_to_int` switch that can contradict bounds
or step semantics. Categorical and log-scale domains can follow numeric
support; unsupported domains must fail explicitly for a given optimizer.

### Stable algorithm IDs

Create ordinary strategy instances with explicit parameters. Do not generate
a new Python class for every proposal or use a call counter as identity.
Top-level, importable strategy classes are compatible with spawned workers.

Assign the algorithm ID from the resolved, typed parameter mapping plus an
explicit strategy-family namespace. The existing `generate_algorithm_id`
helper can be reused with an explicit digest length appropriate to search
size; retain the parameter mapping and detect collisions. Currently generated
IDs use a 32-character digest of the search ID and resolved parameter mapping.
Use a new search ID when the strategy family or evaluation meaning changes.

Generating this ID is a one-time candidate-construction operation. It does
not reintroduce code/parameter manifest checks into checkpoint lookup.

Different raw coordinates resolving to identical parameters identify the same
candidate. Parameter order in a mapping must not affect identity. Store
resolved values, not just the optimizer's raw floating coordinates.

Each optimizer proposal still has a separate proposal ID. Repeated proposals
may reuse a cached evaluation without losing the optimizer's accounting of
which proposal received which observation.

## 6. Optimizer protocol

Prefer a batch-capable ask/tell lifecycle:

```python
class StrategyOptimizer(ABC):
    supported_search_spaces = frozenset()  # "finite", "parameters", or both

    def initialize(self, search_space, direction) -> None: ...

    def ask(self, max_candidates: int) -> Sequence[CandidateProposal]: ...

    def tell(self, observations: Sequence[TrialObservation]) -> None: ...

    def is_finished(self) -> bool: ...

    def state_dict(self) -> dict: ...

    def load_state_dict(self, state: dict) -> None: ...
```

The exported base class marks these six lifecycle methods abstract. Subclass
it, implement every method, and declare supported search spaces.
`OptimizationSearchSpace` exposes `mode`, `algorithm_ids` and `parameters`.

`CandidateProposal` contains a unique optimizer proposal ID and exactly one
of an `algorithm_id` (finite mode) or named numeric `parameters` (generated mode):

```python
CandidateProposal(proposal_id="trial-1", algorithm_id="existing-algorithm")
CandidateProposal(proposal_id="trial-2", parameters={
    "fast_period": 8.2, "slow_period": 42.0, "stop_loss_percentage": 3.1,
})
```

`TrialObservation` contains the proposal ID, the resolved candidate ID,
status, score when valid, and evaluation completeness.

Plugin requirements:

- Whether the optimizer requires an entire generation before `tell`.
- How `ask(max_candidates)` handles a population larger than the admission
  batch. It must not silently resize the population.
- Observations are delivered in proposal order at synchronous batch barriers.
- How constraints, duplicates and exhausted discrete spaces terminate search.
- `state_dict()` returns a finite JSON-serializable dictionary, including
  algorithm version, RNG state and any pending proposals. `load_state_dict()`
  restores it fully and validates the plugin's version.

`ask(max_candidates)` must honor its limit, return unique proposal IDs, and
return at least one proposal when `is_finished()` was false. Population-based
plugins must support staging a larger population across admission batches or
fail explicitly; the framework never silently resizes their population.

`tell` must accept explicit invalid/failed/pruned observations without assuming
every trial has a numerical score. It must be deterministic from saved state
and have no external side effects that would be duplicated on replay.

The original `optimize(fitness_function, bounds, ...)` interface can be
adapted for simple plugins, but a scalar callback does not guarantee batching,
parallel utilization or exact resumability. Those limitations should be
explicit rather than pretending every plugin supports every capability.

## 7. Evaluation coordinator

For each batch:

1. Request proposals within the remaining search budget.
2. Resolve parameters, validate constraints and record proposal identities.
3. Deduplicate evaluations, including candidates already completed on disk.
4. Construct strategies only for candidates needing evaluation.
5. Reuse the bounded backtest runner for the selected study windows.
6. Apply optional window pruning with explicit partial-evaluation status.
7. Select the candidate's intended scalar rows and compute one objective.
8. Persist observations alongside the pre-tell optimizer snapshot.
9. Feed observations to the optimizer, atomically commit the post-tell snapshot,
   and request another batch.

The optimizer runs in the coordinator process. It must not start a second
worker pool on top of the backtest worker pool. Run configuration remains the
single owner of worker count and process-tree memory safeguards.

The initial implementation invokes the existing runner once per proposal batch,
so provider/pool setup may repeat. Reusing prepared setup is a future
performance improvement, not a current guarantee. Preserve
event portfolio isolation. Do not share mutable strategy runtime state across
candidates or windows.

### Budgets

Use `max_evaluations` rather than iterations as the principal cost limit.
Define an evaluation as one newly admitted resolved candidate over the
declared evaluation windows, including an admitted trial that later fails or
is pruned. Cached duplicates and invalid preflight proposals do not consume
that budget; a separate `max_proposals` prevents infinite retries.

Also record actual candidate/window executions, cache hits, elapsed time and
failure counts. This allows fair comparison when algorithms use different
population sizes or prune at different stages.

For example, the supplied CryStAl implementation evaluates its initial
population and each iteration; the supplied random search evaluates only
its iteration samples. Equal iteration counts are not equal budgets.

## 8. Objectives, failures and pruning

### Objective input

Give the objective a `BacktestIndex` scoped to one candidate, the intended
study and engine, and all required completed windows. Do not load full
backtest objects merely to read Sharpe or drawdown.

An algorithm can have both pooled and per-universe rows. Select the intended
rows explicitly; do not arbitrarily score `index.df.iloc[0]`. For a pooled
single-study objective, require exactly one row with `universe_key` unset.

Record the objective name/version, direction, selected metric and aggregation
policy. An aggregate Sharpe is not interchangeable with the mean of
per-window Sharpes. Objectives requiring per-window stability statistics need
explicit scalar window observations; do not assume the final current-window
columns contain the complete window history.

### Trial states

Use a documented state machine:

`proposed -> pending -> running -> complete | invalid | failed | pruned`

- `invalid`: a resolved candidate violates a supplied parameter constraint.
  Malformed proposals, non-finite objectives and plugin errors instead stop
  the search explicitly; they are not silently turned into fitness penalties.
- `failed`: an evaluation error explicitly allowed to continue by policy.
- `pruned`: required windows were intentionally not all evaluated.
- `complete`: all required evaluations finished and the score is finite.

Only complete, valid trials can become the best trial by default.
If a numerical optimizer requires penalties, map statuses at its adapter
boundary with direction-aware semantics. Never persist a placeholder penalty
as though it were measured performance.

Do not blanket-catch every exception in a fitness wrapper. Disk failures,
resource failures and unexpected coordinator errors must stop execution and
preserve durable work. Where `continue_on_error=True` skips a strategy error,
the coordinator must record the missing result as failed, not a successful
empty evaluation. Objective implementation errors should be surfaced.

### Filters

- Keep `window_metrics_filter_function` as the window-boundary pruning hook.
- Keep `final_metrics_filter_function` as final output selection, invoked
  once for the whole search, not once per proposal batch.
- Feed valid scores to the optimizer before final display/output filtering.
- Persist pruning decisions and mark incomplete candidates accordingly.

A top-N window filter sees a batch cohort, not all candidates ever proposed.
Its behavior would therefore depend on optimizer batch composition. Initial
optimization support should allow documented candidate-local pruning rules
or fixed comparison cohorts; unrestricted population-relative pruning needs
a separate explicit policy.

Never compare a pruned candidate's one-window score directly with a complete
candidate's multi-window score without a deliberate multi-fidelity model.

## 9. Persistence, isolation and exact resume

### Evaluation namespaces

Because checkpoints intentionally compare only algorithm/window IDs,
evaluation context must be isolated outside the checkpoint key.

Use separate directories for different engine, study, universe, cost/data
assumptions and train/holdout contexts. For the first release, one search
directory owns one immutable evaluation context.

The search state records the study context, parameter space or candidate IDs,
objective direction, budgets, optimizer class and evaluation settings. These
are validated when reopening the search. Plugin-specific configuration and RNG
state belong in the optimizer snapshot. Context mismatches require a new
search ID; changing worker counts or memory limits is allowed on resume.

This is not automatic source-code hashing. Data providers, strategy code,
factories, objectives and filter callables are not fingerprinted. Use a new
search ID or storage root when their meaning changes. Resume assumes those
inputs remain deterministic and unchanged.

### Current artifacts

```text
<backtest_storage_directory>/optimizations/<search_id>/
  .optimization.lock               # single-writer OS lock
  optimization_state.json          # context, trials, pending batch, snapshot
  backtest_session_index.parquet   # search-wide result index
  batches/
    0/
      checkpoints.json             # unchanged {window_id: [algorithm_ids]}
      <algorithm_id>.obtf
      backtest_session_index.parquet
    1/
      ...
```

Search state must be JSON-serializable; numeric sidecars are not yet supported.
No pickle is loaded. Each batch keeps its own evaluation checkpoints while
the search-wide evaluation cache prevents duplicate candidates across batches.
Use the same configured storage root and search ID to resume; the returned
index directory is the nested search directory, not that root.

When no storage root is configured, a unique root is generated. To resume it,
use `results.directory.parent.parent` as `backtest_storage_directory`.
An existing search cannot be overwritten with `use_checkpoints=False`.
Use a new search ID instead.

The coordinator must accumulate a search-wide index: the existing session
index for one evaluation batch is not automatically the union of all earlier
batches. Trials remain available even if final filtering excludes their
backtest rows.

### Resume ordering

Backtest checkpoints resume expensive evaluations. They do not restore the
optimizer's population, random generator, pending proposals or observations.
Persist both layers.

Use durable journal records and atomic snapshot replacement. Persist proposals
and the post-ask RNG/state before evaluation. Journal complete observations
with sequence numbers before committing a post-tell snapshot with its journal
position.

After interruption:

1. Validate the search context and plugin state version.
2. Restore the last committed optimizer snapshot.
3. Replay committed observations not represented by that snapshot in stable
   order, without applying an observation twice.
4. Reconcile pending evaluations with durable algorithm/window checkpoints.
5. Recover completed metrics or run missing windows, then continue.

Test the crash between bundle persistence and optimizer observation commit.
Exactly-once observation semantics require plugin `tell` to be deterministic
under the restored state, or an explicit idempotence mechanism.

## 10. Statistical safeguards

Use `Study.window_part` and explicitly constructed studies to separate fitting
from assessment. Never optimize against the same held-out test results later
reported as independent evidence.

Recommended workflow:

1. Search training windows with realistic costs and minimum-data constraints.
2. Select candidates using a declared training/validation procedure.
3. Freeze selected parameters.
4. Evaluate on separate untouched out-of-sample windows.
5. Optionally screen with vector execution and validate with event execution
   in a separate evaluation namespace.

Repeated searches over the same validation windows can overfit those windows
too. Report trial counts, selection procedure and window definitions.

Synthetic OHLCV is useful for deterministic integration tests, not evidence of
trading quality. Ensure high >= max(open, close), low <= min(open, close), and
positive volume when producing test bars.

## 11. CryStAl adapter considerations

Before promoting the supplied implementation to a supported plugin:

- Validate finite bounds/scores, step dimensions, probability ranges and
  local-search exponent constraints.
- Handle an entirely invalid population without returning a fictional best.
- Centralize parameter resolution and duplicate evaluation caching.
- Decide whether moves are sequential or generation-based. Current in-place
  updates influence later peers; the original variant's best reference also
  aliases the mutable population.
- Save population, fitness values, global best, iteration position and RNG
  state for resume.
- Compare against seeded random and grid search under equal evaluation
  budgets and identical data/constraints.
- Treat claims of convergence superiority as hypotheses needing measurement.

## 12. Implementation phases and acceptance criteria

### Implemented foundation

Numeric parameters, finite candidate collections, abstract optimizer contracts,
local batch orchestration, event/vector execution, resource controls, trial
statuses and atomic snapshot/replay are included. No concrete optimizer is
included.

### Future: baseline searches

Implement seeded random/grid plugins against the existing contracts.

Tests: bounds, steps, integer types, constraints, duplicate coordinates,
non-finite values, objective direction and bounded termination.

### Phase 2: backtest integration

Add optimization mode to the public runner through a separate coordinator,
reuse existing engine execution and return a search-wide `BacktestIndex`.

Tests for both engines:

- Identical candidates run once per window.
- Worker count/resource controls come only from run configuration.
- Scores select the correct study/engine/universe row.
- Results match equivalent fixed-candidate backtests.
- Returned indexes include earlier batches and survive reopen.
- Failed or pruned candidates never silently become winners.

### Phase 3: durable search resume

Implement namespace validation, journaling, snapshots and replay.

Tests: interrupt after ask, midway through a window, after bundle save, before
and after tell, and during snapshot replacement. Compare resumed seeded
searches with uninterrupted runs, including proposal order and final state.

### Phase 4: richer plugins and objectives

Add a CryStAl adapter, optional external-library adapters, categorical/log
domains and explicitly designed multi-fidelity pruning.

Benchmark candidate throughput, setup overhead, cache reuse, peak memory and
objective quality at equal evaluation budgets. Do not use fitness improvement
on synthetic data as the sole success criterion.

## 13. Recommended first implementation boundary

The current boundary is finite candidate collections or numeric parameter
spaces with a single strategy factory, one engine and immutable study context
per search, synchronous ask/tell batches and one finite scalar objective.
Concrete optimizers and distributed coordination remain separate work.

This establishes the execution and resume contracts before adding algorithm
complexity. It also preserves the central v9 promise: fast ID/window
checkpoint lookup and explicit, persistent index results.
