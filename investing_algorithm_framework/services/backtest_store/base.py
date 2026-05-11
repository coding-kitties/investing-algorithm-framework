"""``BacktestStore`` Protocol + capability mixins (epic #540 phase 3a).

A :class:`BacktestStore` decouples *where* a backtest is persisted
from the rest of the framework. Three concrete implementations are
planned:

* :class:`LocalDirStore` (this PR) — directory of ``.iafbt`` bundles.
  Adapter over today's :meth:`Backtest.save_bundle` /
  :meth:`Backtest.open` so existing layouts keep working unchanged.
* ``LocalTieredStore`` (Phase 3b/3c) — SQLite Tier-1 + per-project
  Parquet datasets (Tier-2) + content-addressed chunks (Tier-3).
* ``FinterionStore`` (closed-source) — HTTP adapter over Finterion's
  hosted tiered backend, with the optional :class:`SupportsRelations`
  capability for strategy-version / report linkage.

The Protocol stays deliberately small. Capabilities that not every
store can or should implement (efficient bulk migration, relational
graph queries, …) are declared as separate Protocols so callers can
``isinstance(store, SupportsCopyFrom)``-test for them at runtime.
"""

from __future__ import annotations

from typing import (
    Iterable,
    Iterator,
    Optional,
    Protocol,
    runtime_checkable,
)

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndexRow,
)


# A handle is an opaque, store-scoped, stable string identifier for a
# single backtest record. For ``LocalDirStore`` it is the bundle path
# relative to the store root; for ``LocalTieredStore`` it will be the
# ``run_id`` (uuid7); for ``FinterionStore`` a remote URI. Callers
# should treat handles as opaque tokens — never parse them.
StoreHandle = str


class StoreError(Exception):
    """Base class for all :class:`BacktestStore` errors."""


class StoreHandleNotFoundError(StoreError, KeyError):
    """Raised when an operation references a handle that does not exist."""


@runtime_checkable
class BacktestStore(Protocol):
    """Minimal write/read/list/delete contract for backtest storage.

    All implementations must be safe for concurrent reads. Concurrent
    writes are implementation-specific (``LocalDirStore`` allows
    them; tiered stores will document their guarantees).

    The contract intentionally mirrors today's
    :meth:`Backtest.save_bundle` / :meth:`Backtest.open` semantics so
    :class:`LocalDirStore` is a 1:1 adapter and existing tests keep
    passing without behavioural drift.
    """

    def write(
        self,
        backtest: Backtest,
        *,
        handle: Optional[StoreHandle] = None,
    ) -> StoreHandle:
        """Persist *backtest* and return its handle.

        If *handle* is supplied the store should write to (or replace)
        that exact location; otherwise the store picks a deterministic
        handle from the backtest's identity (e.g. ``algorithm_id`` for
        local stores, ``run_id`` for tiered stores).
        """
        ...

    def open(
        self,
        handle: StoreHandle,
        *,
        summary_only: bool = False,
    ) -> Backtest:
        """Materialise the backtest at *handle*.

        ``summary_only`` mirrors :meth:`Backtest.open`: when True the
        store should avoid decoding heavy time-series payloads (the
        Tier-2 Parquet bodies, in tiered terminology).
        """
        ...

    def exists(self, handle: StoreHandle) -> bool:
        """Return True if *handle* refers to a stored backtest."""
        ...

    def delete(self, handle: StoreHandle) -> None:
        """Remove the backtest at *handle*. No-op if absent."""
        ...

    def iter_handles(self) -> Iterator[StoreHandle]:
        """Yield every handle currently in the store, in stable order."""
        ...

    def iter_index_rows(self) -> Iterator[BacktestIndexRow]:
        """Yield a :class:`BacktestIndexRow` for every stored backtest.

        Implementations that have a Tier-1 index should serve this
        from the index (no bulk decode); :class:`LocalDirStore`
        falls back to ``Backtest.open(..., summary_only=True)`` per
        bundle when no sidecar index is present.
        """
        ...

    def __len__(self) -> int:
        """Number of backtests currently in the store."""
        ...


# ---------------------------------------------------------------------------
# Optional capabilities — declared as separate Protocols so callers can
# feature-test with isinstance(store, SupportsXxx).
# ---------------------------------------------------------------------------


@runtime_checkable
class SupportsCopyFrom(Protocol):
    """Stores that can ingest from another :class:`BacktestStore`.

    Used by ``iaf migrate-store`` (Phase 3d) to move bundles between
    a :class:`LocalDirStore` and a ``LocalTieredStore`` (or to push
    to ``FinterionStore``). Implementations may optimise — e.g. a
    tiered store can dedup chunks during ingest — but the default
    fallback is a per-handle ``write(src.open(h))`` loop.
    """

    def copy_from(
        self,
        src: "BacktestStore",
        *,
        handles: Optional[Iterable[StoreHandle]] = None,
    ) -> int:
        """Copy backtests from *src* into this store.

        Args:
            src: source store to read from.
            handles: optional subset of handles to copy. If None, all
                handles in *src* are copied.

        Returns:
            Number of backtests successfully copied.
        """
        ...
