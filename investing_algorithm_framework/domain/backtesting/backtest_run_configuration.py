from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Union

from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured
from investing_algorithm_framework.domain.models.snapshot_interval import \
    SnapshotInterval


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _environment_bool(
    environment: Mapping[str, str],
    name: str,
    default: bool,
) -> bool:
    value = environment.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"{name} environment variable {value!r} is not a valid boolean; "
        "use true/false, yes/no, on/off, or 1/0"
    )


def _environment_int(
    environment: Mapping[str, str],
    name: str,
    default: Optional[int],
) -> Optional[int]:
    value = environment.get(name)
    if value is None:
        return default
    if value.strip().lower() == "none":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{name} environment variable {value!r} is not a valid integer"
        ) from exc


@dataclass(frozen=True)
class BacktestRunConfiguration:
    """Operational settings shared by vector and event backtest runs.

    save_filled_data_points opts into storing synthetic filled OHLCV rows
    in the CCXT canonical cache. It only applies when fill_missing_data is
    enabled and data source initialization is not skipped. These rows are
    copied from adjacent candles, not recovered exchange observations, and
    subsequent runs reuse them even with fill_missing_data disabled.
    Other data providers retain their existing persistence behavior.

    execution_backend selects vector execution; event_fill_backend selects
    only event candle matching. event_schedule_backend selects timestamp
    traversal, not schedule generation, tick services, or accounting. All
    default to python; rust is strict and auto permits pre-execution fallback.
    event_state_backend selects sql (default), memory (Python transitions),
    or rust (native cash/position, exit allocation and risk transitions).
    Both experimental archive backends spool execution histories to disk.
    Rust requires a compatible extension; it never falls back mid-run.
    Python retains orchestration, allocation selection, persistence and hooks.
    Active result sets and individual records are not memory bounded.
    """

    continue_on_error: bool = True
    use_checkpoints: bool = True
    backtest_storage_directory: Optional[Union[str, Path]] = None
    show_progress: bool = True
    n_workers: Optional[int] = None
    memory_budget_mb: Optional[int] = None
    min_available_memory_mb: Optional[int] = None
    snapshot_interval: SnapshotInterval = SnapshotInterval.DAILY
    skip_data_sources_initialization: bool = False
    dynamic_position_sizing: bool = False
    fill_missing_data: bool = True
    max_tasks_per_child: Optional[int] = 16
    save_filled_data_points: bool = False
    signal_storage_directory: Optional[Union[str, Path]] = None
    execution_backend: str = 'python'
    hard_memory_limit_mb: Optional[int] = None
    event_fill_backend: str = 'python'
    event_schedule_backend: str = 'python'
    event_state_backend: str = 'sql'

    def __post_init__(self):
        if self.event_state_backend not in ('sql', 'memory', 'rust'):
            raise ValueError('event_state_backend must be sql, memory or rust')
        if self.event_schedule_backend not in ('python', 'rust', 'auto'):
            raise ValueError(
                'event_schedule_backend must be python, rust or auto'
            )
        if self.event_fill_backend not in ('python', 'rust', 'auto'):
            raise ValueError('event_fill_backend must be python, rust or auto')
        if self.execution_backend not in ('python', 'rust', 'auto'):
            raise ValueError('execution_backend must be python, rust or auto')
        if self.hard_memory_limit_mb is not None and (
            type(self.hard_memory_limit_mb) is not int
            or self.hard_memory_limit_mb <= 0
        ):
            raise ValueError('hard_memory_limit_mb must be a positive integer')
        if self.signal_storage_directory is not None:
            object.__setattr__(self, 'signal_storage_directory', str(
                Path(self.signal_storage_directory).expanduser().resolve()
            ))
        if not isinstance(self.save_filled_data_points, bool):
            raise ValueError("save_filled_data_points must be a bool")
        if self.n_workers is not None and self.n_workers < -1:
            raise ValueError("n_workers must be -1, 0, or a positive integer")
        for name in ("memory_budget_mb", "min_available_memory_mb"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if (
            self.max_tasks_per_child is not None
            and self.max_tasks_per_child <= 0
        ):
            raise ValueError("max_tasks_per_child must be greater than zero")
        if not isinstance(self.snapshot_interval, SnapshotInterval):
            raise ValueError("snapshot_interval must be a SnapshotInterval")

    @classmethod
    def from_env(
        cls,
        prefix: str = "IAF_BACKTEST_",
        environment: Optional[Mapping[str, str]] = None,
    ) -> "BacktestRunConfiguration":
        """Create a configuration from ``IAF_BACKTEST_*`` variables."""
        env = os.environ if environment is None else environment
        storage_directory = env.get(f"{prefix}STORAGE_DIRECTORY")
        return cls(
            continue_on_error=_environment_bool(
                env, f"{prefix}CONTINUE_ON_ERROR", True
            ),
            use_checkpoints=_environment_bool(
                env, f"{prefix}USE_CHECKPOINTS", True
            ),
            backtest_storage_directory=storage_directory or None,
            show_progress=_environment_bool(
                env, f"{prefix}SHOW_PROGRESS", True
            ),
            n_workers=_environment_int(
                env, f"{prefix}N_WORKERS", None
            ),
            memory_budget_mb=_environment_int(
                env, f"{prefix}MEMORY_BUDGET_MB", None
            ),
            min_available_memory_mb=_environment_int(
                env, f"{prefix}MIN_AVAILABLE_MEMORY_MB", None
            ),
            snapshot_interval=SnapshotInterval.from_value(
                env.get(f"{prefix}SNAPSHOT_INTERVAL", "DAILY")
            ),
            skip_data_sources_initialization=_environment_bool(
                env, f"{prefix}SKIP_DATA_SOURCES_INITIALIZATION", False
            ),
            dynamic_position_sizing=_environment_bool(
                env, f"{prefix}DYNAMIC_POSITION_SIZING", False
            ),
            fill_missing_data=_environment_bool(
                env, f"{prefix}FILL_MISSING_DATA", True
            ),
            max_tasks_per_child=_environment_int(
                env, f"{prefix}MAX_TASKS_PER_CHILD", 16
            ),
            save_filled_data_points=_environment_bool(
                env, f"{prefix}SAVE_FILLED_DATA_POINTS", False
            ),
            signal_storage_directory=env.get(
                f'{prefix}SIGNAL_STORAGE_DIRECTORY'),
            execution_backend=env.get(f'{prefix}EXECUTION_BACKEND', 'python'),
            event_fill_backend=env.get(
                f'{prefix}EVENT_FILL_BACKEND', 'python'),
            event_schedule_backend=env.get(
                f'{prefix}EVENT_SCHEDULE_BACKEND', 'python'),
            event_state_backend=env.get(f'{prefix}EVENT_STATE_BACKEND', 'sql'),
            hard_memory_limit_mb=_environment_int(
                env, f'{prefix}HARD_MEMORY_LIMIT_MB', None
            ),
        )
