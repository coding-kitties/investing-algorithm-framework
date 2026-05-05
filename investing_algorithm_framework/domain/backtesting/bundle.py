"""Single-file binary bundle persistence for :class:`Backtest`.

Implements the bundle format proposed in issue #487:

- One ``.iafbt`` file per backtest (zstd-compressed MessagePack).
- Optional content-addressed Parquet store for OHLCV payloads, shared
  across many bundles in the same parent directory.
- Round-trips perfectly through :py:meth:`Backtest.to_dict` /
  :py:meth:`Backtest.from_dict`.

The directory format produced by :py:meth:`Backtest.save` is preserved
as a fall-back; this module never touches it.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import msgpack
import zstandard as zstd

from .backtest import Backtest

logger = logging.getLogger(__name__)


BUNDLE_FORMAT_VERSION = 1
BUNDLE_EXT = ".iafbt"

# ``zstd`` compression level. Level 7 is a sweet spot: ~6-8x on the
# typical run.json/metrics.json payload, ~10ms encode for a 17MB doc.
_ZSTD_LEVEL = 7

# Header used to detect bundle files cheaply without decoding.
# 4 bytes magic ("IAFB") + 4 bytes little-endian uint32 format version.
_MAGIC = b"IAFB"


# ---------------------------------------------------------------------------
# OHLCV side-store (content-addressed Parquet)
# ---------------------------------------------------------------------------


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _df_to_parquet_bytes(df: Any) -> bytes:
    """Serialize a pandas/polars DataFrame to zstd-compressed Parquet."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Accept polars DataFrames transparently.
    if hasattr(df, "to_pandas") and not hasattr(df, "to_records"):
        df = df.to_pandas()

    table = pa.Table.from_pandas(df, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd", compression_level=5)
    return buf.getvalue()


def _parquet_bytes_to_df(payload: bytes):
    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(payload))
    return table.to_pandas()


def _write_ohlcv_to_store(
    ohlcv: Dict[str, Any],
    store_dir: Union[str, Path],
) -> Dict[str, str]:
    """Write each (symbol, timeframe) DataFrame to *store_dir* keyed by
    content hash. Returns a manifest mapping the original key to the
    relative path of the stored Parquet blob.
    """
    if not ohlcv:
        return {}

    store_dir = Path(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, str] = {}
    for key, df in ohlcv.items():
        if df is None:
            continue
        payload = _df_to_parquet_bytes(df)
        digest = _hash_bytes(payload)
        rel = f"{digest}.parquet"
        target = store_dir / rel
        if not target.exists():
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(payload)
            os.replace(tmp, target)
        manifest[key] = rel
    return manifest


class LazyOhlcvDict(Dict[str, Any]):
    """Dict-like view that loads OHLCV Parquet blobs on first access.

    Iteration / ``.keys()`` / ``len`` work without decoding any blob.
    Reads decode + cache the DataFrame in memory.
    """

    def __init__(
        self,
        manifest: Dict[str, str],
        store_dir: Union[str, Path],
    ):
        super().__init__()
        self._manifest = dict(manifest or {})
        self._store_dir = Path(store_dir)
        self._cache: Dict[str, Any] = {}

    def __contains__(self, key: object) -> bool:  # type: ignore[override]
        return key in self._manifest

    def __iter__(self):
        return iter(self._manifest)

    def __len__(self) -> int:
        return len(self._manifest)

    def keys(self):  # type: ignore[override]
        return self._manifest.keys()

    def __getitem__(self, key: str):
        if key in self._cache:
            return self._cache[key]
        rel = self._manifest[key]
        path = self._store_dir / rel
        df = _parquet_bytes_to_df(path.read_bytes())
        self._cache[key] = df
        return df

    def get(self, key, default=None):  # type: ignore[override]
        if key not in self._manifest:
            return default
        return self[key]


# ---------------------------------------------------------------------------
# Bundle save / open
# ---------------------------------------------------------------------------


def _msgpack_default(obj):
    """Fall-back encoder for objects msgpack does not know natively.

    Handles pandas ``NA`` / ``NaT``, numpy scalars, datetime/date,
    ``Decimal`` and any object exposing ``to_dict()`` / ``isoformat()``.
    """
    # pandas NA / NaT and numpy NaN-likes
    try:
        import pandas as pd
        if obj is pd.NA or (hasattr(obj, "__bool__") and pd.isna(obj)):
            return None
    except (ImportError, ValueError, TypeError):
        pass

    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    try:
        import numpy as np
        if isinstance(obj, np.generic):
            return obj.item()
    except ImportError:
        pass

    from decimal import Decimal
    if isinstance(obj, Decimal):
        return str(obj)

    import uuid
    if isinstance(obj, uuid.UUID):
        return str(obj)

    if isinstance(obj, (set, frozenset)):
        return list(obj)

    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:  # pragma: no cover - best effort
            pass

    # Last-resort fallback: stringify. We never want bundle persistence
    # to crash a long backtest run because of an opaque parameter.
    try:
        return repr(obj)
    except Exception:  # pragma: no cover
        raise TypeError(
            f"Object of type {type(obj).__name__} is not msgpack-serializable"
        )


def _encode_payload(doc: dict) -> bytes:
    raw = msgpack.packb(
        doc,
        use_bin_type=True,
        datetime=False,
        default=_msgpack_default,
    )
    cctx = zstd.ZstdCompressor(level=_ZSTD_LEVEL)
    body = cctx.compress(raw)
    return _MAGIC + BUNDLE_FORMAT_VERSION.to_bytes(4, "little") + body


def _decode_payload(blob: bytes) -> dict:
    if not blob.startswith(_MAGIC):
        raise ValueError(
            "Not a valid Backtest bundle (missing IAFB magic bytes)."
        )
    version = int.from_bytes(blob[4:8], "little")
    if version > BUNDLE_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported bundle format version {version}; this version "
            f"of investing_algorithm_framework supports up to "
            f"{BUNDLE_FORMAT_VERSION}."
        )
    dctx = zstd.ZstdDecompressor()
    raw = dctx.decompress(blob[8:])
    return msgpack.unpackb(raw, raw=False)


def save_bundle(
    backtest: Backtest,
    path: Union[str, Path],
    *,
    include_ohlcv: bool = False,
    ohlcv_store: Optional[Union[str, Path]] = None,
) -> Path:
    """Write *backtest* to a single ``.iafbt`` bundle.

    Args:
        backtest: The :class:`Backtest` to persist.
        path: Destination path. If it is a directory, the file is
            written as ``<path>/<algorithm_id_or_hash>.iafbt``.
            Otherwise the path is used as-is (with ``.iafbt`` appended
            if the suffix is missing).
        include_ohlcv: When True, OHLCV blobs attached to
            ``backtest.ohlcv`` are written to ``ohlcv_store`` (defaulting
            to a sibling ``ohlcv/`` directory next to the bundle) using
            content-addressed Parquet, and a manifest is embedded in
            the bundle.
        ohlcv_store: Override for the OHLCV store directory. Useful
            when persisting many bundles to share a single store.

    Returns:
        The final bundle file path.
    """
    path = Path(path)
    if path.is_dir():
        name = backtest.algorithm_id or "backtest"
        target = path / f"{name}{BUNDLE_EXT}"
    else:
        target = path if path.suffix == BUNDLE_EXT else path.with_suffix(
            path.suffix + BUNDLE_EXT if path.suffix else BUNDLE_EXT
        )
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = {
        "format_version": BUNDLE_FORMAT_VERSION,
        "backtest": backtest.to_dict(),
    }

    if include_ohlcv and getattr(backtest, "ohlcv", None):
        store = (
            Path(ohlcv_store)
            if ohlcv_store is not None
            else target.parent / "ohlcv"
        )
        manifest = _write_ohlcv_to_store(backtest.ohlcv, store)
        if manifest:
            try:
                rel_store = os.path.relpath(store, target.parent)
            except ValueError:
                rel_store = str(store)
            doc["ohlcv"] = {
                "store_dir": rel_store,
                "manifest": manifest,
            }

    payload = _encode_payload(doc)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, target)
    return target


def open_bundle(
    path: Union[str, Path],
    *,
    ohlcv_store: Optional[Union[str, Path]] = None,
) -> Backtest:
    """Load a :class:`Backtest` from a ``.iafbt`` bundle file.

    Args:
        path: Path to the bundle file.
        ohlcv_store: Override for the OHLCV store directory. Defaults
            to the value persisted in the bundle, resolved relative to
            the bundle's parent directory.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Bundle file not found: {path}")

    doc = _decode_payload(path.read_bytes())
    backtest = Backtest.from_dict(doc.get("backtest") or {})

    ohlcv_meta = doc.get("ohlcv")
    if ohlcv_meta:
        manifest = ohlcv_meta.get("manifest") or {}
        store = (
            Path(ohlcv_store)
            if ohlcv_store is not None
            else (path.parent / ohlcv_meta.get("store_dir", "ohlcv")).resolve()
        )
        backtest.ohlcv = LazyOhlcvDict(manifest, store)

    return backtest


def is_bundle_file(path: Union[str, Path]) -> bool:
    """Return True if *path* exists and starts with the bundle magic."""
    p = Path(path)
    if not p.is_file():
        return False
    try:
        with open(p, "rb") as fh:
            return fh.read(4) == _MAGIC
    except OSError:
        return False


# Public re-export for convenience.
__all__ = [
    "BUNDLE_EXT",
    "BUNDLE_FORMAT_VERSION",
    "LazyOhlcvDict",
    "is_bundle_file",
    "open_bundle",
    "save_bundle",
]
