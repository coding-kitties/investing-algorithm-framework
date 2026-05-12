"""``iaf migrate-store`` — copy backtests between :class:`BacktestStore`
implementations using the :class:`SupportsCopyFrom` capability.

Phase 3d of epic #540.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from investing_algorithm_framework.services.backtest_store import (
    BacktestStore,
    LocalDirStore,
    LocalTieredStore,
    SupportsCopyFrom,
)


_STORE_FACTORIES = {
    "local-dir": lambda root: LocalDirStore(root),
    "local-tiered": lambda root: LocalTieredStore(root),
}


def _build_store(kind: str, root: str) -> BacktestStore:
    if kind not in _STORE_FACTORIES:
        raise ValueError(
            f"unknown store kind {kind!r}; expected one of "
            f"{sorted(_STORE_FACTORIES)}"
        )
    return _STORE_FACTORIES[kind](root)


def migrate_store(
    *,
    src_kind: str,
    src_root: str,
    dst_kind: str,
    dst_root: str,
    handles: Optional[list] = None,
) -> int:
    """Copy backtests from one store to another.

    Args:
        src_kind: One of ``"local-dir"``, ``"local-tiered"``.
        src_root: Path to the source store root.
        dst_kind: Same vocabulary as ``src_kind``.
        dst_root: Path to the destination store root.
        handles: Optional subset of source handles to copy. When
            ``None`` every handle in the source is copied.

    Returns:
        The number of backtests written to the destination.

    Raises:
        TypeError: When the destination store does not implement
            :class:`SupportsCopyFrom`.
    """
    src = _build_store(src_kind, src_root)
    Path(dst_root).mkdir(parents=True, exist_ok=True)
    dst = _build_store(dst_kind, dst_root)
    if not isinstance(dst, SupportsCopyFrom):
        raise TypeError(
            f"destination store {dst_kind!r} does not implement "
            f"SupportsCopyFrom"
        )
    return dst.copy_from(src, handles=handles)
