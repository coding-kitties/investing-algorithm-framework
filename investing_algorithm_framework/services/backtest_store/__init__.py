"""Storage abstraction for backtests (epic #540 phase 3).

A :class:`BacktestStore` is the single seam between the framework and
*where* backtest results actually live. Phase 3a ships the Protocol
and a thin :class:`LocalDirStore` adapter over the existing ``.iafbt``
layout, so every consumer (HTML report, ``iaf list/rank``, the MCP
server, future ``FinterionStore``) can be written against one
interface.

See ``docs/design/tiered-backtest-storage.md`` §7 and the Phase 3
plan in epic #540 for the full architecture.
"""

from .base import (
    BacktestStore,
    StoreHandle,
    StoreError,
    StoreHandleNotFoundError,
    SupportsCopyFrom,
)
from .local_dir_store import LocalDirStore

__all__ = [
    "BacktestStore",
    "StoreHandle",
    "StoreError",
    "StoreHandleNotFoundError",
    "SupportsCopyFrom",
    "LocalDirStore",
]
