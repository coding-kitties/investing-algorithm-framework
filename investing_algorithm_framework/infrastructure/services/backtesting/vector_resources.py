"""Soft memory admission control and bounded, recyclable spawn pools."""

from contextlib import contextmanager
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from itertools import chain
import multiprocessing
import os
from pathlib import Path
import threading
from time import monotonic

from investing_algorithm_framework.domain import OperationalException


class BacktestResourceError(OperationalException):
    """A resumable sweep stopped by its soft resource safeguard."""


_THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "POLARS_MAX_THREADS",
)
_SPAWN_ENVIRONMENT_LOCK = threading.RLock()
_MB = 1024 * 1024


@contextmanager
def spawn_thread_limits():
    # Spawn imports numerical libraries before running the initializer.
    # Keep overrides in place through recycling, not just pool construction.
    with _SPAWN_ENVIRONMENT_LOCK:
        previous = {key: os.environ.get(key) for key in _THREAD_ENVIRONMENT}
        try:
            for key in _THREAD_ENVIRONMENT:
                os.environ[key] = "1"
            yield
        finally:
            for key, value in previous.items():
                # Do not overwrite an unrelated thread's intervening change.
                if os.environ.get(key) != "1":
                    continue
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _cgroup_available():
    """Read effective memory headroom, including enclosing Linux cgroups."""
    membership = Path("/proc/self/cgroup")
    if not membership.exists():
        return None
    candidates = []
    for line in membership.read_text().splitlines():
        _, controllers, relative = line.split(":", 2)
        if not controllers:
            root = Path("/sys/fs/cgroup")
            names = ("memory.max", "memory.current")
        elif "memory" in controllers.split(","):
            root = Path("/sys/fs/cgroup/memory")
            names = ("memory.limit_in_bytes", "memory.usage_in_bytes")
        else:
            continue
        # The namespace root may already be the process's cgroup mount.
        candidates.append((root, names))
        current = root / relative.lstrip("/")
        if ".." in current.parts:
            continue
        while current != root and root in current.parents:
            candidates.append((current, names))
            current = current.parent
    available = None
    for directory, (limit_name, used_name) in candidates:
        try:
            raw_limit = (directory / limit_name).read_text().strip()
            if raw_limit == "max":
                continue
            limit = int(raw_limit)
            if limit >= 2 ** 60:
                continue
            used = int((directory / used_name).read_text().strip())
        except FileNotFoundError:
            continue
        headroom = max(0, limit - used)
        available = headroom if available is None else min(available, headroom)
    return available


@dataclass(frozen=True)
class MemorySample:
    rss: int
    available: int
    coordinator_rss: int
    largest_child_rss: int


class MemoryGuard:
    """Conservative RSS accounting; not an OS-enforced memory limit."""

    def __init__(self, memory_budget_mb=None, min_available_memory_mb=None):
        self.budget = (
            memory_budget_mb * _MB if memory_budget_mb is not None else None
        )
        self.reserve = (min_available_memory_mb or 0) * _MB
        self.enabled = (
            memory_budget_mb is not None or min_available_memory_mb is not None
        )
        self._last_check = None

    def check_periodically(self):
        """Check long-running event loops without polling on every bar."""
        if not self.enabled:
            return
        now = monotonic()
        if self._last_check is None or now - self._last_check >= 0.25:
            self.require()
            self._last_check = now

    def sample(self):
        import psutil

        try:
            process = psutil.Process()
            parent_rss = process.memory_info().rss
            rss, largest = parent_rss, 0
            for child in process.children(recursive=True):
                try:
                    child_rss = child.memory_info().rss
                except psutil.NoSuchProcess:
                    continue
                rss += child_rss
                largest = max(largest, child_rss)
            available = psutil.virtual_memory().available
            cgroup_available = _cgroup_available()
            if cgroup_available is not None:
                available = min(available, cgroup_available)
        except (psutil.Error, OSError, ValueError) as exc:
            raise BacktestResourceError(
                "Cannot monitor backtest memory safely; completed checkpoints "
                "remain resumable."
            ) from exc
        return MemorySample(rss, available, parent_rss, largest)

    def fits(self, sample, additional=0):
        return (
            (self.budget is None or sample.rss + additional <= self.budget)
            and sample.available - additional >= self.reserve
        )

    def require(self, additional=0):
        if not self.enabled:
            return None
        sample = self.sample()
        if not self.fits(sample, additional):
            raise BacktestResourceError(
                "Backtest soft memory safeguard stopped the sweep: "
                f"RSS={sample.rss / _MB:.1f} MiB, "
                f"available={sample.available / _MB:.1f} MiB. "
                "No further task can be admitted safely. Completed "
                "checkpoints are durable; resume with more memory, fewer "
                "workers, or a smaller data/window workload."
            )
        return sample


def bounded_process_map(
    worker, arguments, consume, *, initializer, initargs, n_workers,
    max_tasks_per_child, guard,
):
    """Consume each result before admitting replacement work.

    Explicit pool generations work on Python 3.10 as well as newer Python,
    avoiding executor recycling deadlocks and version-specific constructor
    options. A generation admits at most max_tasks_per_child tasks in total,
    so no individual process can exceed that bound.
    """
    arguments = iter(arguments)
    exhausted = False
    calibrated = not guard.enabled
    estimated_worker = 0
    while not exhausted:
        try:
            first = next(arguments)
        except StopIteration:
            break
        arguments = chain((first,), arguments)
        del first
        sample = guard.require()
        if guard.enabled:
            # Initially allow only one worker and reserve a conservative
            # process-sized allowance for imports and copied provider data.
            estimated_worker = max(
                estimated_worker, sample.coordinator_rss, 64 * _MB
            )
            guard.require(estimated_worker)
            capacity = 1
            if calibrated:
                while capacity < n_workers and guard.fits(
                    sample, estimated_worker * (capacity + 1)
                ):
                    capacity += 1
        else:
            capacity = n_workers
        quota = max_tasks_per_child
        if not calibrated:
            quota = 1
        admitted = 0
        pressure = False
        pending = set()
        with spawn_thread_limits():
            with ProcessPoolExecutor(
                max_workers=capacity,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=initializer,
                initargs=initargs,
            ) as executor:
                try:
                    while True:
                        if guard.enabled:
                            sample = guard.sample()
                            estimated_worker = max(
                                estimated_worker, sample.largest_child_rss
                            )
                            pressure = pressure or not guard.fits(sample)
                        while (
                            not pressure and not exhausted
                            and len(pending) < capacity
                            and (quota is None or admitted < quota)
                        ):
                            try:
                                args = next(arguments)
                            except StopIteration:
                                exhausted = True
                                break
                            pending.add(executor.submit(worker, args))
                            del args
                            admitted += 1
                        if not pending:
                            break
                        done, _ = wait(
                            pending, timeout=0.1,
                            return_when=FIRST_COMPLETED,
                        )
                        del _
                        while done:
                            future = done.pop()
                            pending.remove(future)
                            result = future.result()
                            del future
                            consume(result)
                            del result
                finally:
                    for future in pending:
                        future.cancel()
                    pending.clear()
        calibrated = True
        # Running allocations cannot safely be killed. Drain and checkpoint
        # them, reclaim the pool, then either resume smaller or fail clearly.
        if pressure:
            n_workers = max(1, capacity // 2)
            guard.require()
            if capacity == 1:
                raise BacktestResourceError(
                    "A single backtest worker exceeded the soft memory "
                    "safeguard. Completed checkpoints are resumable; increase "
                    "memory or reduce the data/window workload."
                )
