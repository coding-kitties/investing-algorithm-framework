import gc
import os
import unittest
import weakref
from concurrent.futures import Future
from unittest.mock import patch

from investing_algorithm_framework.infrastructure.services.backtesting \
    import vector_resources as resources


def _identity(value):
    return value


def _pid(value):
    return os.getpid(), os.environ.get("OPENBLAS_NUM_THREADS"), value


class _Payload:
    pass


class TestBoundedVectorResources(unittest.TestCase):
    def test_bounded_futures_are_released_before_replacement(self):
        future_refs, payload_refs, generation_sizes = [], [], []
        consumed = []

        class Executor:
            def __init__(self, **kwargs):
                self.admitted = 0
                self.capacity = kwargs["max_workers"]
                # Python 3.10 supports this constructor contract.
                self_test.assertNotIn("max_tasks_per_child", kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                generation_sizes.append(self.admitted)

            def submit(self, function, argument):
                gc.collect()
                alive = sum(ref() is not None for ref in future_refs)
                self_test.assertLess(alive, self.capacity)
                self_test.assertLessEqual(
                    sum(ref() is not None for ref in payload_refs),
                    self.capacity,
                )
                future = Future()
                payload = _Payload()
                future.set_result(payload)
                future_refs.append(weakref.ref(future))
                payload_refs.append(weakref.ref(payload))
                self.admitted += 1
                return future

        self_test = self
        with patch.object(resources, "ProcessPoolExecutor", Executor):
            resources.bounded_process_map(
                _identity, range(101), lambda result: consumed.append(1),
                initializer=None, initargs=(), n_workers=3,
                max_tasks_per_child=7, guard=resources.MemoryGuard(),
            )
        gc.collect()
        self.assertEqual(len(consumed), 101)
        self.assertLessEqual(max(generation_sizes), 7)
        self.assertTrue(all(ref() is None for ref in future_refs))
        self.assertTrue(all(ref() is None for ref in payload_refs))

    def test_real_spawn_recycles_and_limits_import_threads(self):
        results = []
        previous = os.environ.get("OPENBLAS_NUM_THREADS")
        resources.bounded_process_map(
            _pid, range(3), results.append, initializer=None, initargs=(),
            n_workers=1, max_tasks_per_child=1,
            guard=resources.MemoryGuard(),
        )
        self.assertEqual(len({result[0] for result in results}), 3)
        self.assertEqual({result[1] for result in results}, {"1"})
        self.assertEqual(os.environ.get("OPENBLAS_NUM_THREADS"), previous)

    def test_environment_restored_on_failure(self):
        with patch.dict(os.environ, {"OPENBLAS_NUM_THREADS": "13"}):
            with self.assertRaisesRegex(RuntimeError, "failure"):
                with resources.spawn_thread_limits():
                    self.assertEqual(os.environ["OPENBLAS_NUM_THREADS"], "1")
                    raise RuntimeError("failure")
            self.assertEqual(os.environ["OPENBLAS_NUM_THREADS"], "13")

    def test_preflight_rejects_pressure(self):
        guard = resources.MemoryGuard(memory_budget_mb=1)
        with patch.object(
            guard, "sample",
            return_value=resources.MemorySample(2 ** 21, 2 ** 30, 2 ** 21, 0),
        ), self.assertRaisesRegex(
            resources.BacktestResourceError, "checkpoints are durable"
        ):
            guard.require()

    def test_pool_error_propagates(self):
        with patch.object(
            resources, "ProcessPoolExecutor",
            side_effect=RuntimeError("pool failed"),
        ), self.assertRaisesRegex(RuntimeError, "pool failed"):
            resources.bounded_process_map(
                _identity, [1], lambda _: None, initializer=None,
                initargs=(), n_workers=1, max_tasks_per_child=2,
                guard=resources.MemoryGuard(),
            )

    def test_empty_work_does_not_start_or_budget_a_worker(self):
        guard = resources.MemoryGuard(memory_budget_mb=1)
        with patch.object(guard, "require") as require, patch.object(
            resources, "ProcessPoolExecutor",
        ) as executor:
            resources.bounded_process_map(
                _identity, [], lambda _: None, initializer=None,
                initargs=(), n_workers=2, max_tasks_per_child=1, guard=guard,
            )
        executor.assert_not_called()
        require.assert_not_called()

    def test_pressure_drains_then_restarts_with_fewer_workers(self):
        guard = resources.MemoryGuard(memory_budget_mb=1024)
        state = {"capacity": 0, "generation": 0, "consumed": 0}
        capacities = []

        class Executor:
            def __init__(self, **kwargs):
                self.capacity = kwargs["max_workers"]

            def __enter__(self):
                state["generation"] += 1
                state["capacity"] = self.capacity
                capacities.append(self.capacity)
                return self

            def __exit__(self, *args):
                state["capacity"] = 0

            def submit(self, function, argument):
                future = Future()
                future.set_result(argument)
                return future

        def sample():
            rss_mb = 128 * (1 + state["capacity"])
            if state["generation"] == 2 and state["capacity"] \
                    and state["consumed"] >= 5:
                rss_mb = 1200
            return resources.MemorySample(
                rss_mb * 2 ** 20, 4096 * 2 ** 20,
                128 * 2 ** 20, 128 * 2 ** 20,
            )

        def consume(result):
            state["consumed"] += 1

        with patch.object(guard, "sample", side_effect=sample), patch.object(
            resources, "ProcessPoolExecutor", Executor,
        ):
            resources.bounded_process_map(
                _identity, range(12), consume, initializer=None,
                initargs=(), n_workers=4, max_tasks_per_child=16, guard=guard,
            )
        self.assertEqual(capacities, [1, 4, 2])
        self.assertEqual(state["consumed"], 12)

    def test_cgroup_ancestor_limit_is_respected(self):
        from pathlib import Path

        files = {
            "/proc/self/cgroup": "0::/work/job\n",
            "/sys/fs/cgroup/memory.max": "4096",
            "/sys/fs/cgroup/memory.current": "1024",
            "/sys/fs/cgroup/work/memory.max": "2048",
            "/sys/fs/cgroup/work/memory.current": "1536",
            "/sys/fs/cgroup/work/job/memory.max": "max",
        }

        def read(path):
            if str(path) not in files:
                raise FileNotFoundError(path)
            return files[str(path)]

        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", autospec=True, side_effect=read,
        ):
            self.assertEqual(resources._cgroup_available(), 512)

    def test_process_and_cgroup_memory_are_conservative(self):
        import psutil
        guard = resources.MemoryGuard(min_available_memory_mb=10)
        with patch.object(resources, "_cgroup_available", return_value=1):
            sample = guard.sample()
        self.assertEqual(sample.available, 1)
        self.assertGreaterEqual(
            sample.rss, psutil.Process().memory_info().rss - 2 ** 20
        )
        self.assertFalse(guard.fits(sample))
