"""``LocalDirStore`` — directory-of-bundles :class:`BacktestStore`.

Thin adapter over the existing ``.iafbt`` storage layout. Every
backtest is one bundle file under the store's *root* directory.
Optionally maintains a sidecar :class:`SqliteBacktestIndex` to serve
:meth:`iter_index_rows` without re-decoding bundles on every call.

This is the Phase-3a default; it preserves today's on-disk layout
exactly so existing consumers (HTML report, ``iaf list/rank``, the
MCP server) work unchanged.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

from investing_algorithm_framework.domain import (
    Backtest,
    BacktestIndexRow,
    BUNDLE_EXT,
)
from investing_algorithm_framework.services.backtest_index import (
    SqliteBacktestIndex,
)

from .base import (
    BacktestStore,
    StoreError,
    StoreHandle,
    StoreHandleNotFoundError,
)

logger = logging.getLogger(__name__)


SIDECAR_INDEX_NAME = "index.sqlite"


class LocalDirStore(BacktestStore):
    """A directory of ``.iafbt`` bundles, addressable by relative path.

    Handles are bundle paths *relative to the store root* — e.g.
    ``"my_strategy.iafbt"`` or ``"sweep_a/run_03.iafbt"``. Relative
    handles keep the store portable: moving the root directory does
    not invalidate any handle.

    The store optionally maintains a sidecar
    ``<root>/index.sqlite`` (built lazily on the first call to
    :meth:`iter_index_rows` when ``use_index=True``) so listing /
    ranking does not have to re-open every bundle.
    """

    def __init__(
        self,
        root: Union[str, Path],
        *,
        use_index: bool = True,
    ) -> None:
        """
        Args:
            root: directory that holds (or will hold) the bundles.
                Created if it does not exist.
            use_index: when True, :meth:`iter_index_rows` is served
                from a sidecar :class:`SqliteBacktestIndex`. Disable
                for one-shot scripts that never list.
        """
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._use_index = use_index

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _resolve(self, handle: StoreHandle) -> Path:
        """Map *handle* to an absolute path under :attr:`root`.

        Rejects handles that escape the store root (path traversal).
        """
        candidate = (self.root / handle).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StoreError(
                f"handle {handle!r} resolves outside the store root "
                f"{self.root}"
            ) from exc
        return candidate

    @staticmethod
    def _ensure_bundle_suffix(handle: StoreHandle) -> StoreHandle:
        if handle.endswith(BUNDLE_EXT):
            return handle
        return handle + BUNDLE_EXT

    def _default_handle(self, backtest: Backtest) -> StoreHandle:
        """Pick a deterministic handle when the caller didn't supply one.

        Uses ``algorithm_id`` if set, otherwise falls back to a
        timestamp-derived name. The choice is deliberate: the
        Phase 3a contract is "behaves like ``Backtest.save_bundle``";
        callers who need stronger identity (``run_id``, content
        hash, …) should pass an explicit handle.
        """
        if backtest.algorithm_id:
            stem = str(backtest.algorithm_id)
        else:
            from datetime import datetime, timezone
            stem = "backtest_" + datetime.now(timezone.utc).strftime(
                "%Y%m%dT%H%M%S%f"
            )
        return self._ensure_bundle_suffix(stem)

    def _iter_bundle_paths(self) -> Iterator[Path]:
        for p in sorted(self.root.rglob(f"*{BUNDLE_EXT}")):
            if p.is_file():
                yield p

    # ------------------------------------------------------------------
    # BacktestStore API
    # ------------------------------------------------------------------
    def write(
        self,
        backtest: Backtest,
        *,
        handle: Optional[StoreHandle] = None,
    ) -> StoreHandle:
        if handle is None:
            handle = self._default_handle(backtest)
        else:
            handle = self._ensure_bundle_suffix(handle)
        target = self._resolve(handle)
        target.parent.mkdir(parents=True, exist_ok=True)
        backtest.save_bundle(target)
        return handle

    def open(
        self,
        handle: StoreHandle,
        *,
        summary_only: bool = False,
    ) -> Backtest:
        handle = self._ensure_bundle_suffix(handle)
        target = self._resolve(handle)
        if not target.is_file():
            raise StoreHandleNotFoundError(handle)
        return Backtest.open(str(target), summary_only=summary_only)

    def exists(self, handle: StoreHandle) -> bool:
        try:
            target = self._resolve(self._ensure_bundle_suffix(handle))
        except StoreError:
            return False
        return target.is_file()

    def delete(self, handle: StoreHandle) -> None:
        handle = self._ensure_bundle_suffix(handle)
        try:
            target = self._resolve(handle)
        except StoreError:
            return
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            # Shouldn't happen for .iafbt, but tolerate legacy
            # directory-style bundles for symmetry.
            shutil.rmtree(target)

    def iter_handles(self) -> Iterator[StoreHandle]:
        for p in self._iter_bundle_paths():
            yield str(p.relative_to(self.root))

    def __len__(self) -> int:
        return sum(1 for _ in self._iter_bundle_paths())

    def __contains__(self, handle: object) -> bool:
        if not isinstance(handle, str):
            return False
        return self.exists(handle)

    # ------------------------------------------------------------------
    # iter_index_rows — backed by a sidecar SqliteBacktestIndex when
    # ``use_index=True`` (the default), otherwise a per-call decode.
    # ------------------------------------------------------------------
    def iter_index_rows(self) -> Iterator[BacktestIndexRow]:
        if not self._use_index:
            yield from self._iter_index_rows_decoded()
            return

        index_path = self.root / SIDECAR_INDEX_NAME
        # Build or refresh incrementally — same machinery as `iaf index`.
        index = (
            SqliteBacktestIndex.open(index_path)
            if index_path.is_file()
            else SqliteBacktestIndex.create(index_path)
        )
        try:
            for path in self._iter_bundle_paths():
                stat = path.stat()
                rel = str(path.relative_to(self.root))
                if not index.is_up_to_date(
                    rel, stat.st_mtime_ns, stat.st_size,
                ):
                    try:
                        bt = Backtest.open(str(path), summary_only=True)
                        row = bt.index_row(bundle_path=rel)
                        index.upsert(
                            row,
                            bundle_mtime_ns=stat.st_mtime_ns,
                            bundle_size=stat.st_size,
                        )
                    except Exception as exc:  # pragma: no cover - logged
                        logger.warning(
                            "Skipping bundle %s while building index: %s",
                            path, exc,
                        )
                        continue
            yield from index.iter_rows()
        finally:
            index.close()

    def _iter_index_rows_decoded(self) -> Iterator[BacktestIndexRow]:
        for path in self._iter_bundle_paths():
            rel = str(path.relative_to(self.root))
            try:
                bt = Backtest.open(str(path), summary_only=True)
            except Exception as exc:  # pragma: no cover - logged
                logger.warning(
                    "Skipping bundle %s while listing: %s", path, exc,
                )
                continue
            yield bt.index_row(bundle_path=rel)

    # ------------------------------------------------------------------
    # SupportsCopyFrom
    # ------------------------------------------------------------------
    def copy_from(
        self,
        src: BacktestStore,
        *,
        handles: Optional[Iterable[StoreHandle]] = None,
    ) -> int:
        n = 0
        chosen = list(handles) if handles is not None else list(
            src.iter_handles()
        )
        for h in chosen:
            try:
                bt = src.open(h)
            except StoreHandleNotFoundError:
                logger.warning("copy_from: handle %r not in source", h)
                continue
            self.write(bt, handle=h)
            n += 1
        return n

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"LocalDirStore(root={str(self.root)!r}, "
            f"use_index={self._use_index})"
        )

    def __fspath__(self) -> str:
        return os.fspath(self.root)
