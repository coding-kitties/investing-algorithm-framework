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

The developer-provided objective defines what a successful candidate means.
The optimizer proposes parameters, the framework runs the resulting strategy
and calculates its metrics, and then the objective converts those results into
one finite score. The optimizer receives that score through `tell()` and can
use it when choosing later proposals. The optimizer does not need to implement
financial metric calculations itself.

The objective receives a `BacktestIndex` scoped to one candidate algorithm
after all its required study windows have completed. `direction` determines
whether larger or smaller objective scores are preferred. A random optimizer
can retain the scores for ranking without adapting its proposals; Bayesian,
evolutionary and other adaptive optimizers can use them to influence later
proposals.

The candidate index is not the full `Backtest` object. It is a lightweight
table containing:

- The current candidate's algorithm ID and resolved parameters.
- Study, engine and universe identity.
- Scalar summary metrics aggregated using the study's existing semantics.
- The bundle path needed to load the full backtest and its individual runs.

An index can contain more than one row for the same algorithm, such as a pooled
row plus per-universe rows. Select the intended study, engine and universe
explicitly rather than assuming the first row is the desired summary.

### Score from summary metrics

Use the index columns when the objective only needs existing cross-window
summary metrics. This avoids decoding the full backtest bundle:


```python
import math


def score_candidate(index):
    pooled = index.df.loc[
        index.df["universe_key"].isna()
        & (index.df["study_name"] == training_study.name)
        & (index.df["engine_type"] == "vector")
    ]
    if len(pooled) != 1:
        raise ValueError("Expected exactly one pooled candidate row")

    score = float(pooled["summary.sharpe_ratio"].iloc[0])
    if not math.isfinite(score):
        raise ValueError("Candidate has no finite Sharpe ratio")
    return score
```

In this example, the candidate's objective score is its existing aggregate
Sharpe ratio. There is no separate built-in "robustness score." A developer
who wants to optimize Sortino, Calmar, total return, drawdown or a documented
combination selects or combines the corresponding summary columns in this
function.

Objective exceptions and non-finite scores stop the search explicitly. They are
not silently converted to penalties. The final window's `window_*` columns are
not a history of every window; use `summary.*` metrics for aggregate objectives.
Reading scalar metrics does not require loading full backtest bundles.

### Score from individual run metrics

When the objective intentionally depends on individual windows, load the one
backtest bundle referenced by the candidate index and select the same study and
engine. Every run exposes its own `backtest_metrics`:

```python
import math
from statistics import fmean, pstdev


def score_candidate_windows(index):
    backtest = next(index.iter_backtests())
    completed_study = backtest.get_study(training_study.name)
    runs = completed_study.get_runs(engine="vector")

    if len(runs) != len(training_study.backtest_windows):
        raise ValueError("Candidate did not complete every study window")

    returns = []
    for run in runs:
        metrics = run.backtest_metrics
        value = float(metrics.total_net_gain_percentage)
        if not math.isfinite(value):
            raise ValueError("Window has no finite return")
        returns.append(value)

    # Project-specific example: reward mean return and penalize instability.
    return fmean(returns) - pstdev(returns)
```

This formula is an example policy, not a framework-defined robustness metric.
Its units are decimal return: `0.12` means 12%. With only a few windows, avoid
presenting a custom composite as statistically conclusive. Other objectives
might use the weakest window, require a minimum closed-trade count, or combine
an existing summary ratio with explicitly documented run-level diagnostics.

Loading bundles is more expensive than reading summary columns, so prefer the
summary-only objective unless the optimization decision genuinely requires
window-specific values. Individual run metrics remain available after the
search for comparison and diagnosis even when the objective uses only a
summary metric.

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

## Initial candidate seed and bounded alternatives

Use `initial_parameters` when a compatible optimizer must propose known
settings before its ordinary search candidates. Initial points count toward
the existing proposal and evaluation budgets; they are not extra evaluations.
The number of configured initial points therefore cannot exceed either budget.

Here, an **initial candidate seed** means a known parameter mapping—typically
the strategy's current baseline settings—that must be evaluated first. It is
different from the optimizer's random-number seed:

- `initial_parameters=[baseline_search_parameters]` supplies the baseline
  candidate to evaluate first.
- `RandomSearchOptimizer(seed=42)` makes the later random alternatives
  reproducible.

Either concept can exist without the other. Changing the initial candidate
changes the search identity; changing the random seed changes the optimizer's
ordinary proposal sequence and should also use a new search ID.

The optimizer must opt in by overriding `set_initial_parameters()`. It owns the
points from then on and emits them through its normal `ask()` lifecycle. The
framework does not inject external observations into `tell()`.

This minimal random-search plugin preserves its queue and random generator in
its checkpoint state:

```python
import random

from investing_algorithm_framework import (
    CandidateProposal,
    FloatParameter,
    IntegerParameter,
    StrategyOptimizer,
)


def nested_tuple(value):
    if isinstance(value, list):
        return tuple(nested_tuple(item) for item in value)
    return value


class RandomSearchOptimizer(StrategyOptimizer):
    supported_search_spaces = frozenset({"parameters"})

    def __init__(self, seed):
        self.seed = seed

    def initialize(self, search_space, direction):
        self.search_space = search_space
        self.random = random.Random(self.seed)
        self.initial = []
        self.proposal_number = 0

    def set_initial_parameters(self, initial_parameters):
        self.initial = [dict(values) for values in initial_parameters]

    def ask(self, max_candidates):
        proposals = []
        while self.initial and len(proposals) < max_candidates:
            proposals.append(CandidateProposal(
                proposal_id=f"candidate-{self.proposal_number}",
                parameters=self.initial.pop(0),
            ))
            self.proposal_number += 1
        while len(proposals) < max_candidates:
            values = {}
            for parameter in self.search_space.parameters:
                if isinstance(parameter, IntegerParameter):
                    values[parameter.name] = self.random.randint(
                        parameter.lower, parameter.upper,
                    )
                elif isinstance(parameter, FloatParameter):
                    values[parameter.name] = self.random.uniform(
                        parameter.lower, parameter.upper,
                    )
            proposals.append(CandidateProposal(
                proposal_id=f"candidate-{self.proposal_number}",
                parameters=values,
            ))
            self.proposal_number += 1
        return proposals

    def tell(self, observations):
        pass

    def is_finished(self):
        return False

    def state_dict(self):
        return {
            "initial": self.initial,
            "proposal_number": self.proposal_number,
            "random_state": self.random.getstate(),
        }

    def load_state_dict(self, state):
        self.initial = [dict(values) for values in state["initial"]]
        self.proposal_number = state["proposal_number"]
        self.random.setstate(nested_tuple(state["random_state"]))
```

Configure one baseline plus at most nine alternatives:

```python
optimization = OptimizationConfiguration(
    search_id="exploratory-screen-v1",
    optimizer=RandomSearchOptimizer(seed=42),
    initial_parameters=[baseline_search_parameters],
    parameters=search_parameters,
    strategy_factory=build_strategy,
    objective=score_candidate,
    direction="maximize",
    max_evaluations=10,
    max_proposals=100,
)

results = app.run_backtest(
    study=three_window_study,
    optimization=optimization,
    run_configuration=run_configuration,
)
```

The baseline is the first proposal and can consume one of the ten distinct
evaluation slots. Every admitted candidate uses the same three study windows.
Duplicate or constraint-rejected proposals still consume proposal slots, so
the search can finish with fewer than ten completed candidates.

The baseline and every alternative use the same `score_candidate` objective.
After each candidate completes all three windows, the framework supplies that
candidate's index to the objective and sends the returned score to the
optimizer. Initial candidates do not receive special scoring treatment; their
only special behavior is guaranteed proposal order.

Initial mappings must contain exactly the declared parameter names. Values use
the same clamping, grid resolution, constraints and deduplication as ordinary
proposals. A plugin that does not override `set_initial_parameters()` fails
configuration explicitly. The framework also rejects a compatible plugin that
does not emit the resolved initial points first and in order.

Changing initial points changes the persisted search identity and therefore
cannot resume an existing `search_id`. On resume, the framework reconstructs
the initial queue before loading the optimizer snapshot; the plugin's
`state_dict()` must preserve how far that queue and its ordinary sequence have
advanced.

Inspect the existing cross-window summaries first, scoped to the pooled row for
the configured study and engine:

```python
pooled = results.df.loc[
    results.df["universe_key"].isna()
    & (results.df["study_name"] == three_window_study.name)
    & (results.df["engine_type"] == "vector")
]
print(pooled[[
    "algorithm_id",
    "parameters",
    "summary.total_net_gain_percentage",
    "summary.max_drawdown",
    "summary.number_of_trades_closed",
]].to_string(index=False))
```

Drill into the same engine's individual windows without recomputing another
summary:

```python
for backtest in results.iter_backtests():
    completed_study = backtest.get_study(three_window_study.name)
    for run in completed_study.get_runs(engine="vector"):
        metrics = run.backtest_metrics
        print(
            backtest.algorithm_id,
            run.backtest_start_date,
            metrics.total_net_gain_percentage,
            metrics.max_drawdown,
            metrics.number_of_trades_closed,
            metrics.number_of_trades_open_at_end,
        )
```

Percentage metrics are decimals. The summary drawdown is an aggregate study
metric, not the worst run-level drawdown, and independent window returns must
not be presented as a compounded portfolio return. The returned index contains
successful candidates; inspect trial statuses when diagnosing rejected,
failed, or pruned proposals rather than silently treating them as missing data.

## Implement your optimizer

Subclass the exported `StrategyOptimizer` and implement all six abstract
methods. Override `set_initial_parameters()` only when the plugin supports
ordered initial parameter points:

```python
from investing_algorithm_framework import StrategyOptimizer


class MyOptimizer(StrategyOptimizer):
    supported_search_spaces = frozenset({"finite"})

    def set_initial_parameters(self, initial_parameters):
        raise NotImplementedError

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

When configured, `set_initial_parameters(initial_parameters)` runs immediately
after `initialize`, including before a saved optimizer snapshot is restored.
Compatible plugins must queue those mappings ahead of ordinary proposals and
include the remaining queue in `state_dict()`. Finite-search plugins do not
support initial parameter mappings.

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
