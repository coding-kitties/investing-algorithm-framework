---
sidebar_position: 13
sidebar_label: Backtest Optimization
---

# Backtest Optimization

Use a pluggable optimizer to choose which algorithms or parameter combinations
to backtest. The framework handles evaluation, checkpoints, resource controls
and persistent results; your optimizer handles search decisions.

Both `app.run_backtest()` and `app.run_backtests()` accept an
`OptimizationConfiguration` and return a `BacktestIndex`.

:::info Current scope

The framework provides base classes, local batch execution and optimizer-state
resume. It does **not** bundle random search, grid search, CryStAl, Bayesian
optimization or other concrete optimizers. Supply your own `StrategyOptimizer`
subclass. Distributed execution is not implemented by this API.

:::

## Why use an optimizer?

A fixed sweep evaluates every supplied candidate. An optimizer can select a
smaller subset or generate new candidates, using previous scores when its
search algorithm supports adaptation.

Optimization can reduce the number of expensive evaluations. It does not
automatically make an individual backtest faster, nor guarantee that a smaller
search finds the best parameters.

| Mechanism | Responsibility |
| --- | --- |
| Optimizer | Choose which candidates to evaluate next |
| Objective | Assign a numerical score to a completed candidate |
| Parameter constraint | Reject invalid parameter combinations before evaluation |
| Window metrics filter | Stop selected candidates from continuing through later windows |
| Final metrics filter | Select which completed results appear in the returned index |

For example, pruning 500 candidates after their first window can save work on
later windows, but it cannot recover the cost of that first window. An optimizer
with a 100-evaluation budget can instead admit at most 100 distinct candidates
over the declared study windows, including candidates that fail or are pruned.

## Separate experiment, execution and search

| Object | Configuration |
| --- | --- |
| `Study` | Universe, engine, capital and evaluation windows |
| `BacktestRunConfiguration` | Storage, checkpoints, progress, workers and memory |
| `OptimizationConfiguration` | Candidate space, optimizer, objective and search budgets |

The examples below assume you have configured an `app`, a `training_study` with
data providers, and a compatible optimizer instance. See
[Vector Backtesting](./vector-backtesting.md) for study and execution setup.

## Define an objective

The objective receives a `BacktestIndex` scoped to one candidate and its study
and engine, after all required windows have completed. Return one finite
number; `direction` determines whether larger or smaller scores are preferred.

Indexes can contain both pooled and per-universe rows. Select the intended row
explicitly rather than assuming the first row represents the whole evaluation:

```python
import math


def score_candidate(index):
    pooled = index.df.loc[index.df["universe_key"].isna()]
    if len(pooled) != 1:
        raise ValueError("Expected exactly one pooled candidate row")

    score = float(pooled["summary.sharpe_ratio"].iloc[0])
    if not math.isfinite(score):
        raise ValueError("Candidate has no finite Sharpe ratio")
    return score
```

Objective exceptions and non-finite scores stop the search explicitly. They are
not silently converted to penalties. The final window's `window_*` columns are
not a history of every window; use `summary.*` metrics for aggregate objectives.
Reading scalar metrics does not require loading full backtest bundles.

## Mode 1: search existing algorithms

Supply a finite collection and an optimizer declaring support for `"finite"`:

```python
from investing_algorithm_framework import (
    BacktestRunConfiguration,
    OptimizationConfiguration,
)

run_configuration = BacktestRunConfiguration(
    backtest_storage_directory="./backtests",
    n_workers=8,
    memory_budget_mb=16_384,
    min_available_memory_mb=4_096,
)

optimization = OptimizationConfiguration(
    search_id="existing-variants-v1",
    optimizer=my_finite_optimizer,
    objective=score_candidate,
    direction="maximize",
    max_evaluations=100,
    max_proposals=1_000,
    proposal_batch_size=16,
)

results = app.run_backtests(
    algorithms=my_algorithms,
    study=training_study,
    run_configuration=run_configuration,
    optimization=optimization,
)
```

Each algorithm needs an explicit, unique, nonempty `algorithm_id`. You can also
provide `strategies=` or use the singular `algorithm=` or `strategy=` inputs on
`run_backtest()`. Registered strategies are used when no candidates are supplied
and the configuration has no factory.

This mode cannot invent candidates outside the supplied collection. The
optimizer sees their IDs, not an automatically extracted numeric parameter
space. Opaque IDs alone are insufficient for numerical algorithms that need
distances or parameter arithmetic.

Existing engine restrictions still apply: combined multi-strategy algorithms
and algorithms with tasks/hooks require event-driven execution.

## Mode 2: generate parameterized strategies

Supply numeric parameter definitions and a factory instead of an existing
candidate collection:

```python
from investing_algorithm_framework import (
    FloatParameter,
    IntegerParameter,
    OptimizationConfiguration,
)


def build_strategy(params, algorithm_id):
    return MySMAStrategy(
        algorithm_id=algorithm_id,
        fast_period=params["fast_period"],
        slow_period=params["slow_period"],
        stop_loss_percentage=params["stop_loss_percentage"],
    )


def valid_parameters(params):
    return params["fast_period"] < params["slow_period"]


optimization = OptimizationConfiguration(
    search_id="sma-parameters-v1",
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
    objective=score_candidate,
    direction="maximize",
    max_evaluations=200,
)

results = app.run_backtests(
    study=training_study,
    run_configuration=run_configuration,
    optimization=optimization,
)
```

Here `MySMAStrategy` is your own importable `TradingStrategy` subclass accepting
those constructor arguments, and `my_parameter_optimizer` supports
`"parameters"` search spaces.

The factory must return a `TradingStrategy` instance preserving the supplied
algorithm ID. Use ordinary classes, not dynamically generated classes, so
strategies can be sent to spawned workers.

### Parameter resolution

- `IntegerParameter` returns an integer and defaults to a step of `1`.
- `FloatParameter` is continuous by default (`step=0`).
- Finite proposals are clamped to the bounds, then snapped to the nearest
  legal lower-anchored grid point when a step is configured.
- An upper bound is not a legal grid point unless it lies on that grid.
- Proposal names must match the declared parameters exactly.
- Constraints run against resolved values before backtesting.
- Equivalent resolved mappings share a stable algorithm ID within the search.

Factory and parameter definitions must be provided together. Factory mode
cannot be combined with supplied algorithms or strategies. Categorical and
log-scale parameter classes are not currently provided.

## Implement your optimizer

Subclass the exported `StrategyOptimizer` and implement all six abstract
methods:

```python
from investing_algorithm_framework import StrategyOptimizer


class MyOptimizer(StrategyOptimizer):
    supported_search_spaces = frozenset({"finite"})

    def initialize(self, search_space, direction):
        raise NotImplementedError

    def ask(self, max_candidates):
        raise NotImplementedError

    def tell(self, observations):
        raise NotImplementedError

    def is_finished(self):
        raise NotImplementedError

    def state_dict(self):
        raise NotImplementedError

    def load_state_dict(self, state):
        raise NotImplementedError
```

This is a lifecycle template, not a runnable search implementation. Replace the
method bodies with your search logic or calls to an external optimizer library.
Declare `{"parameters"}` or `{"finite", "parameters"}` only if your plugin
actually supports those modes.

### Initialize and propose

`initialize(search_space, direction)` receives an `OptimizationSearchSpace`
with `mode`, `algorithm_ids` and `parameters`. Exactly one candidate source is
nonempty. Initialize the search state here.

`ask(max_candidates)` returns a sequence of `CandidateProposal` objects:

```python
from investing_algorithm_framework import CandidateProposal

finite_proposal = CandidateProposal(
    proposal_id="proposal-1",
    algorithm_id="an-existing-algorithm-id",
)

parameter_proposal = CandidateProposal(
    proposal_id="proposal-2",
    parameters={
        "fast_period": 8.2,
        "slow_period": 42.0,
        "stop_loss_percentage": 3.1,
    },
)
```

Each proposal must contain exactly one of `algorithm_id` or `parameters`.
Proposal IDs must be unique across the whole search, including after resume.
Multiple proposals may refer to the same resolved candidate; its evaluation
can be reused without losing per-proposal observations.

Honor the requested limit and return at least one proposal while the search
is unfinished. Return `True` from `is_finished()` before the next `ask` when
the search is exhausted.

### Receive observations

`tell(observations)` receives `TrialObservation` objects in proposal order:

| Status | Meaning | Score |
| --- | --- | --- |
| `complete` | All required windows completed and the objective was finite | Finite number |
| `invalid` | A parameter constraint rejected the resolved candidate | `None` |
| `failed` | The runner did not produce a complete candidate evaluation | `None` |
| `pruned` | A window filter rejected the candidate | `None` |

Observations include `proposal_id`, `algorithm_id`, `parameters`, `status`,
`score` and `error`. Do not assume every observation has a numerical score.
If an external optimizer requires penalties, translate statuses at the plugin
boundary without pretending that a penalty was measured performance.

Malformed proposals, plugin exceptions, resource errors and persistence errors
stop execution. `continue_on_error` governs errors handled by the backtest
runner, not arbitrary optimizer or objective exceptions.

### Save and restore state

`state_dict()` must return a JSON-serializable dictionary with no non-finite
numbers. Include everything needed to resume: plugin version, RNG state,
population/model state, pending proposals and proposal counters.

`load_state_dict(state)` must restore that state completely and validate its
version. On resume, the framework calls `initialize` before loading the saved
snapshot.

`tell` must be deterministic from restored state and must not rely on
non-idempotent external side effects: a crash after `tell` but before snapshot
commit can cause that batch to be replayed from the pre-tell snapshot.

## Search budgets and parallelism

| Setting | Default | Meaning |
| --- | --- | --- |
| `direction` | `"maximize"` | Prefer larger scores; use `"minimize"` for smaller scores |
| `max_evaluations` | `100` | Limit newly admitted distinct candidates, including failed/pruned evaluations |
| `max_proposals` | `1000` | Limit proposals, including invalid and duplicate proposals |
| `proposal_batch_size` | `16` | Upper bound on proposals requested in one batch |

All three counts must be positive integers. Invalid constraints and cached
duplicates do not consume new evaluation slots. Proposal limits prevent endless
retries when a plugin keeps returning invalid or duplicate candidates.

Execution uses synchronous batch barriers:

```text
ask -> resolve and deduplicate -> bounded backtest workers
    -> persist observations -> tell -> commit optimizer state -> repeat
```

`proposal_batch_size` is **not** a worker count. Worker concurrency comes only
from `BacktestRunConfiguration.n_workers` and available memory. A population
larger than the admission limit must be staged by the plugin without changing
its search semantics; the framework does not silently resize populations.

The optimizer runs in the coordinator process and must not create another
backtest worker pool. Its state contributes to the soft process-tree RSS
budget. The memory guard can reduce admission or stop the run; it is not a
hard OS memory limit.

Full evaluation bundles are persisted while the coordinator retains scalar
results and search state. Provider and worker-pool setup can repeat between
batches in the current implementation. Optimization does not guarantee higher
per-candidate throughput.

## Filters and returned results

Pass `window_metrics_filter_function` and `final_metrics_filter_function`
directly to the app call:

- The window filter sees the current proposal batch at each window boundary.
- Pruned candidates are not scored as complete evaluations.
- The final filter runs on the combined successful results after the search,
  not separately for each batch.
- Final filtering does not remove trial observations from search state.

A top-N window filter compares only its batch cohort, not every candidate ever
proposed. Prefer candidate-local thresholds unless batch-relative selection is
an intentional part of your experiment.

The result is a search-wide `BacktestIndex`, not just the winning candidate:

```python
print(results.df)
print(results.df["algorithm_id"].nunique())

# Load full bundles only when needed.
for backtest in results.iter_backtests():
    print(backtest.algorithm_id)
```

An empty index is possible when no candidate completes successfully or the final
filter rejects all results. It does not imply that a valid winner exists.

## Checkpointing and resume

Search artifacts are stored beneath the configured root:

```text
backtests/
  optimizations/
    existing-variants-v1/
      .optimization.lock
      optimization_state.json
      backtest_session_index.parquet
      batches/
        0/
          checkpoints.json
          backtest_session_index.parquet
          <algorithm_id>.obtf
        1/
          ...
```

Per-batch checkpoints keep the v9 format `{window_id: [algorithm_id, ...]}`.
The search state separately tracks pending work, evaluated candidates, trial
observations and optimizer snapshots. A single-writer OS lock prevents two
coordinators from updating one search concurrently.

To resume, call the same app method with:

- The same configured storage root and `search_id`.
- The same study, candidates or parameter space, budgets and optimizer class.
- A compatible optimizer instance capable of restoring its saved state.
- `BacktestRunConfiguration(use_checkpoints=True)`, which is the default.

Completed candidate/window evaluations are reused. Pending optimizer feedback
is recovered from committed state so observations are not applied twice to the
restored snapshot.

The returned `results.directory` is the nested search directory. Do not pass it
back as the storage root: reuse the original `backtest_storage_directory`.
If you omitted that setting and the framework generated a root, recover it as
`results.directory.parent.parent`.

Worker counts and memory limits can change on resume. Recorded experiment
context mismatches fail explicitly. An existing search cannot be overwritten
with `use_checkpoints=False`; choose a new search ID instead.

:::warning Keep evaluation meaning unchanged

Strategy code, data providers, factories, objectives and filters are not
fingerprinted. Use a new search ID or storage root when their meaning changes.
Stable algorithm IDs and window IDs do not detect changed source code or data.

:::

## Validate beyond the search

Use training windows for optimization and untouched windows for out-of-sample
evaluation. Compare search algorithms under the same evaluation budget and
realistic costs. A larger search can overfit historical data more efficiently;
improved training fitness is not evidence of improved live performance.

For execution details and index filtering examples, continue with
[Vector Backtesting](./vector-backtesting.md).
