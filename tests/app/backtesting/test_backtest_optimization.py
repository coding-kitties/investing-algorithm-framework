import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import pandas as pd

from investing_algorithm_framework import (
    Algorithm, BacktestDateRange, BacktestEngine, BacktestIndex,
    BacktestRunConfiguration, BacktestWindow, CandidateProposal,
    CSVOHLCVDataProvider, IntegerParameter, OperationalException,
    OptimizationConfiguration,
    RESOURCE_DIRECTORY, StrategyOptimizer, Study, Universe, create_app,
)
from investing_algorithm_framework.infrastructure import BacktestService
from investing_algorithm_framework.infrastructure.services.backtesting \
    import optimization as coordinator_module
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_resources import BacktestResourceError
from tests.scenarios.vector_vs_event_backtests.test_event_vs_vector_backtest \
    import CSV_FILENAME, LongCycleStrategy


class ScriptedOptimizer(StrategyOptimizer):
    """Test plugin with fully controlled proposals and serializable state."""

    supported_search_spaces = frozenset({"finite", "parameters"})

    def __init__(self, proposals, crash_after_tell=False):
        self.proposals = proposals
        self.crash_after_tell = crash_after_tell
        self.offset = 0
        self.observations = []

    def initialize(self, search_space, direction):
        self.space = search_space
        self.direction = direction
        self.offset = 0
        self.observations = []

    def ask(self, max_candidates):
        result = self.proposals[self.offset:self.offset + max_candidates]
        self.offset += len(result)
        return result

    def tell(self, observations):
        self.observations.extend(observations)
        if self.crash_after_tell:
            raise KeyboardInterrupt("after tell")

    def is_finished(self):
        return self.offset == len(self.proposals)

    def state_dict(self):
        return {
            "offset": self.offset,
            "observations": [o.to_dict() for o in self.observations],
        }

    def load_state_dict(self, state):
        from investing_algorithm_framework import TrialObservation

        self.offset = state["offset"]
        self.observations = [
            TrialObservation.from_dict(o) for o in state["observations"]
        ]


def build_strategy(params, algorithm_id):
    strategy = LongCycleStrategy(algorithm_id=algorithm_id)
    strategy.parameters = dict(params)
    return strategy


def window_score(index):
    pooled = index.df.loc[index.df["universe_key"].isna()]
    return float(pooled["summary.number_of_windows"].iloc[0])


class OptimizationFixture(TestCase):
    engine = BacktestEngine.VECTOR

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.study = Study(
            name="optimization",
            universe=Universe(
                market="BITVAVO", trading_symbol="EUR", symbols=["BTC"],
            ),
            initial_capital=1000, risk_free_rate=0.03, engines=[self.engine],
            backtest_windows=[
                BacktestWindow(train_range=BacktestDateRange(
                    start_date=datetime(
                        2020, 12, 20, 10, tzinfo=timezone.utc,
                    ) + timedelta(hours=10 * i),
                    end_date=datetime(
                        2020, 12, 20, 10, tzinfo=timezone.utc,
                    ) + timedelta(hours=10 * (i + 1)),
                ))
                for i in range(2)
            ],
        )
        self.run_config = BacktestRunConfiguration(
            backtest_storage_directory=self.directory / "results",
            show_progress=False, continue_on_error=False,
        )
        self.saved = []

    def app(self):
        app = create_app(
            name=uuid4().hex,
            config={RESOURCE_DIRECTORY: str(self.directory)},
        )
        csv = (
            Path(__file__).resolve().parents[2] / "resources" / "test_data"
            / "ohlcv" / CSV_FILENAME
        )
        app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv), symbol="BTC/EUR", time_frame="2h",
            market="BITVAVO", warmup_window=5,
        ), priority=1)
        return app

    def configuration(self, proposals=None, **kwargs):
        if proposals is None:
            proposals = [
                CandidateProposal(f"p-{i}", algorithm_id=key)
                for i, key in enumerate(("a", "b", "c"))
            ]
        return OptimizationConfiguration(
            search_id="search",
            optimizer=ScriptedOptimizer(proposals),
            objective=window_score,
            max_evaluations=3, max_proposals=10,
            proposal_batch_size=2,
            **kwargs,
        )

    def run_search(
        self, configuration, *, interrupt_after=None, candidates=None,
        run_configuration=None, **kwargs,
    ):
        if candidates is None and configuration.strategy_factory is None:
            candidates = {
                "strategies": [
                    LongCycleStrategy(algorithm_id=key)
                    for key in ("a", "b", "c")
                ],
            }
        save = BacktestService._batch_save_and_checkpoint

        def record(service, backtests, date_range, *args, **options):
            save(service, backtests, date_range, *args, **options)
            self.saved.extend(
                (b.algorithm_id, date_range.start_date) for b in backtests
            )
            if interrupt_after is not None and (
                len(self.saved) >= interrupt_after
            ):
                raise KeyboardInterrupt("durable evaluation")

        with patch.object(
            BacktestService, "_batch_save_and_checkpoint", new=record,
        ):
            return self.app().run_backtests(
                **(candidates or {}),
                study=self.study,
                run_configuration=run_configuration or self.run_config,
                optimization=configuration,
                **kwargs,
            )

    def state_path(self):
        return (
            self.directory / "results" / "optimizations" / "search"
            / "optimization_state.json"
        )


class TestVectorOptimization(OptimizationFixture):
    def test_batches_return_all_candidates_and_resume_without_evaluation(self):
        config = self.configuration()
        result = self.run_search(config)
        self.assertEqual(set(result.df["algorithm_id"]), {"a", "b", "c"})
        self.assertEqual(len(self.saved), 6)
        self.assertEqual(
            [o.score for o in config.optimizer.observations], [2, 2, 2],
        )
        self.assertEqual(len(list(result.iter_backtests())), 3)
        reopened = BacktestIndex.open(
            result.directory, filename="backtest_session_index.parquet",
        )
        pd.testing.assert_frame_equal(result.df, reopened.df)
        self.saved.clear()
        fresh = self.configuration()
        resumed = self.run_search(fresh)
        self.assertEqual(self.saved, [])
        self.assertEqual(len(fresh.optimizer.observations), 3)
        pd.testing.assert_frame_equal(result.df, resumed.df)

    def test_window_interruption_restores_pending_batch_and_checkpoints(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_search(self.configuration(), interrupt_after=2)
        completed = set(self.saved)
        self.saved.clear()
        config = self.configuration()
        result = self.run_search(config)
        self.assertFalse(completed & set(self.saved))
        self.assertEqual(len(self.saved), 4)
        self.assertEqual(set(result.df["algorithm_id"]), {"a", "b", "c"})
        self.assertEqual(len(config.optimizer.observations), 3)

    def test_crash_after_tell_replays_from_pre_tell_snapshot(self):
        config = self.configuration()
        config.optimizer.crash_after_tell = True
        with self.assertRaisesRegex(KeyboardInterrupt, "after tell"):
            self.run_search(config)
        self.assertEqual(
            json.loads(self.state_path().read_text())["phase"], "tell",
        )
        self.saved.clear()
        fresh = self.configuration()
        self.run_search(fresh)
        self.assertEqual({key for key, _ in self.saved}, {"c"})
        self.assertEqual(
            [o.proposal_id for o in fresh.optimizer.observations],
            ["p-0", "p-1", "p-2"],
        )

    def test_generated_parameters_deduplicate_and_report_invalid(self):
        proposals = [
            CandidateProposal("p0", parameters={"period": 2.1}),
            CandidateProposal("p1", parameters={"period": 2.2}),
            CandidateProposal("p2", parameters={"period": 3}),
            CandidateProposal("p3", parameters={"period": 4}),
        ]
        config = self.configuration(
            proposals, strategy_factory=build_strategy,
            parameters=[IntegerParameter("period", 1, 10)],
            constraints=[lambda params: params["period"] != 3],
        )
        result = self.run_search(config)
        observations = config.optimizer.observations
        self.assertEqual(
            [o.status for o in observations],
            ["complete", "complete", "invalid", "complete"],
        )
        self.assertEqual(
            observations[0].algorithm_id, observations[1].algorithm_id,
        )
        self.assertEqual(len(set(result.df["algorithm_id"])), 2)
        self.assertEqual(len(self.saved), 4)
        self.saved.clear()
        fresh = replace(config, optimizer=ScriptedOptimizer(proposals))
        self.run_search(fresh)
        self.assertEqual(self.saved, [])

    def test_window_pruning_and_final_filter_have_distinct_scopes(self):
        config = self.configuration()
        window_calls = []

        def window_filter(index, date_range):
            window_calls.append(set(index.df["algorithm_id"]))
            return index.filter(lambda row: row["algorithm_id"] != "b")

        final = Mock(side_effect=lambda index: index.filter(
            lambda row: row["algorithm_id"] == "c",
        ))
        result = self.run_search(
            config, window_metrics_filter_function=window_filter,
            final_metrics_filter_function=final,
        )
        self.assertEqual(set(result.df["algorithm_id"]), {"c"})
        final.assert_called_once()
        self.assertEqual(
            [o.status for o in config.optimizer.observations],
            ["complete", "pruned", "complete"],
        )
        self.assertEqual(window_calls[0], {"a", "b"})
        self.assertEqual(window_calls[-1], {"c"})
        self.assertEqual(
            len([key for key, _ in self.saved if key == "b"]), 1,
        )

    def test_existing_algorithms_keep_their_identity(self):
        algorithms = []
        for key in ("a", "b", "c"):
            algorithm = Algorithm(algorithm_id=key)
            algorithm.add_strategy(LongCycleStrategy(algorithm_id=key))
            algorithms.append(algorithm)
        result = self.run_search(
            self.configuration(), candidates={"algorithms": algorithms},
        )
        self.assertEqual(set(result.df["algorithm_id"]), {"a", "b", "c"})

    def test_real_parallel_workers_and_memory_controls(self):
        config = replace(self.configuration(), max_evaluations=2)
        result = self.run_search(
            config,
            run_configuration=replace(
                self.run_config, n_workers=2, max_tasks_per_child=2,
                min_available_memory_mb=1,
            ),
        )
        self.assertEqual(set(result.df["algorithm_id"]), {"a", "b"})
        self.assertEqual(len(self.saved), 4)


class TestEventOptimization(TestVectorOptimization):
    engine = BacktestEngine.EVENT_DRIVEN


class TestOptimizationSafeguards(OptimizationFixture):
    # Keep these non-engine-specific cases separate from the event matrix.
    def test_context_changes_cannot_resume_an_existing_search(self):
        self.run_search(self.configuration())
        self.study.initial_capital += 1
        with self.assertRaisesRegex(ValueError, "context mismatch"):
            self.run_search(self.configuration())

    def test_no_checkpoint_run_cannot_overwrite_existing_search(self):
        self.run_search(self.configuration())
        with self.assertRaisesRegex(ValueError, "Search already exists"):
            self.run_search(
                self.configuration(),
                run_configuration=replace(
                    self.run_config, use_checkpoints=False,
                ),
            )

    def test_unsupported_modes_and_ambiguous_inputs_fail_before_running(self):
        config = self.configuration()
        config.optimizer.supported_search_spaces = frozenset({"parameters"})
        with self.assertRaisesRegex(ValueError, "does not support"):
            self.run_search(config)
        generated = self.configuration(
            strategy_factory=build_strategy,
            parameters=[IntegerParameter("period", 1, 10)],
        )
        with self.assertRaisesRegex(ValueError, "not both"):
            self.run_search(generated, candidates={
                "strategies": [LongCycleStrategy(algorithm_id="a")],
            })
        self.assertEqual(self.saved, [])

    def test_objective_errors_propagate_and_keep_evaluations_resumable(self):
        objective = Mock(side_effect=ValueError("objective failed"))
        config = replace(self.configuration(), objective=objective)
        with self.assertRaisesRegex(ValueError, "objective failed"):
            self.run_search(config)
        completed = set(self.saved)
        self.saved.clear()
        self.run_search(self.configuration())
        self.assertFalse(completed & set(self.saved))

    def test_nonfinite_objective_is_not_reported_as_success(self):
        config = replace(
            self.configuration(), objective=lambda index: float("nan"),
        )
        with self.assertRaises(ValueError):
            self.run_search(config)
        state = json.loads(self.state_path().read_text())
        self.assertEqual(state["trials"], [])

    def test_memory_errors_are_not_converted_to_fitness_penalties(self):
        config = self.configuration()
        with patch.object(
            coordinator_module.MemoryGuard, "require",
            side_effect=BacktestResourceError("memory pressure"),
        ):
            with self.assertRaisesRegex(BacktestResourceError, "pressure"):
                self.run_search(config)
        self.assertEqual(config.optimizer.observations, [])
        self.assertEqual(self.saved, [])

    def test_atomic_state_failure_preserves_previous_snapshot(self):
        path = self.directory / "state.json"
        original = {"optimizer_state": {"iteration": 1}}
        coordinator_module._save_state(path, original)
        with patch.object(
            coordinator_module.os, "replace", side_effect=OSError("disk full"),
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                coordinator_module._save_state(
                    path, {"optimizer_state": {"iteration": 2}},
                )
        self.assertEqual(json.loads(path.read_text()), original)
        self.assertFalse(path.with_suffix(".json.pending").exists())

    def test_active_search_cannot_have_two_writers(self):
        config = self.configuration()
        directory = self.state_path().parent
        directory.mkdir(parents=True)
        with coordinator_module._search_lock(directory):
            with self.assertRaisesRegex(
                OperationalException, "already in use",
            ):
                self.run_search(config)

    def test_duplicate_candidate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate candidate"):
            self.run_search(self.configuration(), candidates={
                "strategies": [
                    LongCycleStrategy(algorithm_id="a"),
                    LongCycleStrategy(algorithm_id="a"),
                ],
            })

    def test_failed_candidate_is_not_scored(self):
        config = self.configuration()
        coordinator = coordinator_module.OptimizationCoordinator(
            runner=Mock(return_value=coordinator_module.make_index(
                self.directory, [],
            )),
            configuration=config, run_configuration=self.run_config,
            study=deepcopy(self.study), resource_directory=self.directory,
            strategies=[LongCycleStrategy(algorithm_id=k) for k in "abc"],
        )
        index = coordinator.run()
        self.assertEqual(len(index), 0)
        self.assertEqual(
            [o.status for o in config.optimizer.observations],
            ["failed", "failed", "failed"],
        )
