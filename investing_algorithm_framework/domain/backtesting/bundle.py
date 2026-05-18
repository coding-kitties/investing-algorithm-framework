"""Single-file binary bundle persistence for :class:`Backtest`.

Implements the bundle format proposed in issue #487, plus the v2
extensions described in ``docs/design/bundle-format-v2.md``.

Format versions
---------------

- **v1** (legacy): a single zstd-compressed MessagePack envelope of
  ``{"format_version": 1, "backtest": <Backtest.to_dict()>,
  "ohlcv": <optional manifest>}``. Heavy time-series fields
  (equity / drawdown / monthly / yearly / cumulative_return /
  rolling_sharpe / TWR variants) live inline as lists of
  ``(value, ISO-string)`` tuples.

- **v2** (default since v8.9.0):
    - Splits runs into ``vector_runs`` / ``event_runs`` based on
      ``Backtest.engine_type``; the matching summary metrics live
      under ``vector_metrics`` / ``event_metrics``. Bundles with no
      engine_type fall back to ``backtest_runs``.
    - Heavy time series are extracted from each ``backtest_metrics``
      dict and stored as embedded Parquet bytes under a top-level
      ``blobs`` map keyed ``runs/<idx>/metrics/<field>.parquet``.
      Each blob has two columns: ``ts`` (int64 epoch-ms in UTC) and
      ``value`` (float64). Yearly returns store ``ts`` as a date
      midnight epoch-ms. The original field is replaced with a
      ``{"@blob": "<key>"}`` reference.
    - On read, blob references are resolved back to lists of
      ``(value, datetime)`` tuples so consumers see the same shape
      as v1. ``open_bundle(..., summary_only=True)`` skips the
      Parquet decode entirely (the references are left in place
      as opaque dicts), which keeps bulk-listing fast.

OHLCV side store and the ``LazyOhlcvDict`` are unchanged across
versions. The OHLCV writer accepts ``float32_ohlcv=True`` to
quantize OHLCV columns to float32 before Parquet encoding.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import msgpack
import zstandard as zstd

from .backtest import Backtest

logger = logging.getLogger(__name__)


# Bumped to 2 when v2 format went live (issue #538). Writers always
# emit v2 unless ``save_bundle(..., format_version=1)`` is requested
# explicitly. Readers accept both v1 and v2.
BUNDLE_FORMAT_VERSION = 2
BUNDLE_EXT = ".iafbt"

# ``zstd`` compression level. Level 19 is the highest level still in
# the "fast" tier (i.e. without ``--ultra``). Measured on real
# 7-run/2192-snapshot bundles it cuts ~14% off the on-disk size vs
# level 7 with no observable decode-speed impact, and is what we
# default to since the v8.9 size review.
_ZSTD_LEVEL = 19

# Header used to detect bundle files cheaply without decoding.
# 4 bytes magic ("IAFB") + 4 bytes little-endian uint32 format version.
_MAGIC = b"IAFB"


# Metric fields that are extracted into Parquet blobs in format v2.
# All of these have shape ``List[Tuple[float, datetime|date]]`` in
# ``BacktestMetrics.to_dict()``; any non-list value is left untouched.
_METRIC_BLOB_FIELDS: Tuple[str, ...] = (
    "equity_curve",
    "drawdown_series",
    "cumulative_return_series",
    "rolling_sharpe_ratio",
    "monthly_returns",
    "yearly_returns",
    "twr_equity_curve",
    "twr_drawdown_series",
)

# Marker key inserted in place of an extracted heavy series. The
# top-level ``blobs`` dict resolves the key to the actual Parquet
# bytes. Kept as a single-key dict so any consumer that walks the
# document without resolving blobs can still distinguish a reference
# from real data.
_BLOB_REF_KEY = "@blob"


# ---------------------------------------------------------------------------
# OHLCV side-store (content-addressed Parquet)
# ---------------------------------------------------------------------------


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _df_to_parquet_bytes(df: Any, *, float32: bool = False) -> bytes:
    """Serialize a pandas/polars DataFrame to zstd-compressed Parquet.

    Args:
        df: Source DataFrame (pandas or polars).
        float32: When True, downcast any float64 columns to float32
            before encoding. For OHLCV payloads this typically
            halves on-disk size with no observable effect on backtest
            metrics. Use only for OHLCV / market data; metric series
            keep float64 to preserve precision.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Accept polars DataFrames transparently.
    if hasattr(df, "to_pandas") and not hasattr(df, "to_records"):
        df = df.to_pandas()

    if float32:
        try:
            import numpy as np
            float_cols = df.select_dtypes(include=[np.float64]).columns
            if len(float_cols) > 0:
                df = df.astype({c: np.float32 for c in float_cols})
        except Exception:  # pragma: no cover - numpy/pandas optional path
            pass

    table = pa.Table.from_pandas(df, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd", compression_level=5)
    return buf.getvalue()


def _parquet_bytes_to_df(payload: bytes):
    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(payload))
    return table.to_pandas()


# ---------------------------------------------------------------------------
# v2 metric-series Parquet helpers (small two-column blobs)
# ---------------------------------------------------------------------------


def _to_epoch_ms(value: Any) -> Optional[int]:
    """Return *value* as an int64 UTC epoch-millisecond timestamp.

    Accepts ``datetime``, ``date``, ISO-8601 strings, and pre-converted
    ints. Returns None for None / unparseable inputs so the encoder can
    drop them without raising.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        # Already epoch-ms (assume — we never write ints into the
        # series ourselves; this branch only fires on weird inputs).
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return int(value.timestamp() * 1000)
    if isinstance(value, date):
        # midnight UTC for the calendar day
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return int(dt.timestamp() * 1000)
    return None


def _from_epoch_ms(ts_ms: Optional[int]) -> Optional[datetime]:
    """Inverse of :func:`_to_epoch_ms`. Returns timezone-aware UTC."""
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)


def _series_to_parquet_bytes(series: Any) -> Optional[bytes]:
    """Encode a ``[(value, datetime), ...]`` series as 2-column Parquet.

    Returns None if the series is empty or not a list of pairs (the
    caller then leaves the field inline — i.e. blob extraction is a
    no-op and the original list is preserved).
    """
    if not isinstance(series, (list, tuple)) or not series:
        return None

    timestamps = []
    values = []
    for entry in series:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return None
        value, ts = entry
        ts_ms = _to_epoch_ms(ts)
        if ts_ms is None:
            return None
        timestamps.append(ts_ms)
        try:
            values.append(float(value) if value is not None else None)
        except (TypeError, ValueError):
            return None

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({
        "ts": pa.array(timestamps, type=pa.int64()),
        "value": pa.array(values, type=pa.float64()),
    })
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd", compression_level=5)
    return buf.getvalue()


def _parquet_bytes_to_series(payload: bytes) -> list:
    """Inverse of :func:`_series_to_parquet_bytes`. Returns
    ``[(value, iso_string), ...]`` matching the v1 inline shape so
    downstream consumers (``BacktestMetrics.from_dict``) don't need
    to know which format produced the bundle.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(payload))
    ts_col = table.column("ts").to_pylist()
    value_col = table.column("value").to_pylist()
    out = []
    for i in range(len(ts_col)):
        dt = _from_epoch_ms(ts_col[i])
        iso = dt.isoformat() if dt is not None else None
        out.append((value_col[i], iso))
    return out


def _write_ohlcv_to_store(
    ohlcv: Dict[str, Any],
    store_dir: Union[str, Path],
    *,
    float32: bool = False,
) -> Dict[str, str]:
    """Write each (symbol, timeframe) DataFrame to *store_dir* keyed by
    content hash. Returns a manifest mapping the original key to the
    relative path of the stored Parquet blob.

    When ``float32=True``, OHLCV float64 columns are downcast to
    float32 before encoding (~2x size reduction with no observable
    impact on backtest metrics for crypto/equity time series).
    """
    if not ohlcv:
        return {}

    store_dir = Path(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, str] = {}
    for key, df in ohlcv.items():
        if df is None:
            continue
        payload = _df_to_parquet_bytes(df, float32=float32)
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

    def values(self):  # type: ignore[override]
        for k in self._manifest:
            yield self[k]

    def items(self):  # type: ignore[override]
        for k in self._manifest:
            yield k, self[k]

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


def _encode_payload(doc: dict, *, format_version: int) -> bytes:
    raw = msgpack.packb(
        doc,
        use_bin_type=True,
        datetime=False,
        default=_msgpack_default,
    )
    cctx = zstd.ZstdCompressor(level=_ZSTD_LEVEL)
    body = cctx.compress(raw)
    return _MAGIC + format_version.to_bytes(4, "little") + body


def _decode_payload(blob: bytes) -> Tuple[int, dict]:
    """Decode a bundle byte string and return ``(format_version, doc)``.

    Both v1 and v2 envelopes share the same outer ``IAFB`` + uint32
    version header and the same zstd-compressed msgpack body — only
    the *contents* of ``doc`` differ.
    """
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
    return version, msgpack.unpackb(raw, raw=False)


# ---------------------------------------------------------------------------
# v2 envelope construction / disassembly
# ---------------------------------------------------------------------------


def _extract_metric_blobs(
    backtest_dict: dict,
    blobs: Dict[str, bytes],
    *,
    runs_key: str,
) -> None:
    """Walk ``backtest_dict[runs_key]`` and replace heavy metric series
    with ``{"@blob": "<key>"}`` references; the actual Parquet bytes
    are appended to *blobs* keyed by ``runs/<idx>/metrics/<field>.parquet``.

    Mutates *backtest_dict* in place. Fields that aren't recognised
    list-of-tuples shapes are left inline (the encoder is conservative
    by design — never lose data).
    """
    runs = backtest_dict.get(runs_key)
    if not runs:
        return
    for idx, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        metrics = run.get("backtest_metrics")
        if not isinstance(metrics, dict):
            continue
        for field in _METRIC_BLOB_FIELDS:
            series = metrics.get(field)
            if series is None:
                continue
            payload = _series_to_parquet_bytes(series)
            if payload is None:
                # Unrecognised shape — keep inline as v1 fallback.
                continue
            key = f"runs/{idx}/metrics/{field}.parquet"
            blobs[key] = payload
            metrics[field] = {_BLOB_REF_KEY: key}


def _resolve_metric_blobs(
    backtest_dict: dict,
    blobs: Dict[str, bytes],
    *,
    runs_key: str,
    summary_only: bool = False,
) -> None:
    """Inverse of :func:`_extract_metric_blobs`: walk
    ``backtest_dict[runs_key]`` and replace any
    ``{"@blob": "<key>"}`` reference with the decoded series.

    When ``summary_only=True``, references are replaced with empty
    lists instead of being decoded — this keeps the
    ``BacktestMetrics.from_dict`` contract (it expects lists for
    these fields, not refs) while skipping the Parquet decode cost.
    The scalar summary fields (sharpe / sortino / max_dd / etc.)
    on the same metrics object remain fully populated, which is the
    whole point of this mode.
    """
    runs = backtest_dict.get(runs_key)
    if not runs:
        return
    for run in runs:
        if not isinstance(run, dict):
            continue
        metrics = run.get("backtest_metrics")
        if not isinstance(metrics, dict):
            continue
        for field in _METRIC_BLOB_FIELDS:
            value = metrics.get(field)
            if isinstance(value, dict) and _BLOB_REF_KEY in value:
                if summary_only:
                    metrics[field] = []
                    continue
                key = value[_BLOB_REF_KEY]
                payload = blobs.get(key)
                if payload is None:
                    metrics[field] = []
                else:
                    metrics[field] = _parquet_bytes_to_series(payload)


def _build_v2_envelope(backtest: Backtest) -> dict:
    """Build the ``doc`` dict for a v2 bundle from *backtest*.

    Routes runs and summary into engine-specific slots
    (``vector_runs`` / ``vector_metrics`` / ``event_runs`` /
    ``event_metrics``) when ``backtest.engine_type`` is set, else
    falls back to the engine-agnostic ``backtest_runs`` /
    ``backtest_summary`` keys (compatible with consumers that don't
    care about the engine).
    """
    backtest_dict = backtest.to_dict()
    blobs: Dict[str, bytes] = {}

    engine = backtest.engine_type
    envelope: Dict[str, Any] = {
        "format_version": 2,
        "engine_type": engine,
        "algorithm_id": backtest_dict.get("algorithm_id"),
        "metadata": backtest_dict.get("metadata") or {},
        "risk_free_rate": backtest_dict.get("risk_free_rate"),
        "strategy_ids": backtest_dict.get("strategy_ids") or [],
        "parameters": backtest_dict.get("parameters") or {},
        "tag": backtest_dict.get("tag"),
        "backtest_permutation_tests":
            backtest_dict.get("backtest_permutation_tests"),
    }

    if engine == "vector":
        runs_key = "vector_runs"
        metrics_key = "vector_metrics"
    elif engine == "event":
        runs_key = "event_runs"
        metrics_key = "event_metrics"
    else:
        runs_key = "backtest_runs"
        metrics_key = "backtest_summary"

    envelope[runs_key] = backtest_dict.get("backtest_runs")
    envelope[metrics_key] = backtest_dict.get("backtest_summary")

    _extract_metric_blobs(envelope, blobs, runs_key=runs_key)

    if blobs:
        envelope["blobs"] = blobs
    return envelope


def _envelope_to_backtest_dict(doc: dict) -> dict:
    """Inverse of :func:`_build_v2_envelope`: collapse the v2 envelope
    back into the engine-agnostic dict shape consumed by
    :py:meth:`Backtest.from_dict`. Resolves embedded blob references
    (unless the caller passed ``summary_only`` upstream — in that case
    the references are preserved as opaque dicts).
    """
    engine = doc.get("engine_type")
    if engine == "vector":
        runs_key = "vector_runs"
        metrics_key = "vector_metrics"
    elif engine == "event":
        runs_key = "event_runs"
        metrics_key = "event_metrics"
    else:
        runs_key = "backtest_runs"
        metrics_key = "backtest_summary"

    return {
        "algorithm_id": doc.get("algorithm_id"),
        "backtest_runs": doc.get(runs_key),
        "backtest_summary": doc.get(metrics_key),
        "backtest_permutation_tests":
            doc.get("backtest_permutation_tests"),
        "metadata": doc.get("metadata") or {},
        "risk_free_rate": doc.get("risk_free_rate"),
        "strategy_ids": doc.get("strategy_ids") or [],
        "parameters": doc.get("parameters") or {},
        "tag": doc.get("tag"),
        "engine_type": engine,
    }


def save_bundle(
    backtest: Backtest,
    path: Union[str, Path],
    *,
    include_ohlcv: bool = False,
    ohlcv_store: Optional[Union[str, Path]] = None,
    format_version: Optional[int] = None,
    float32_ohlcv: bool = False,
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
        format_version: Force a specific bundle format. Defaults to
            :data:`BUNDLE_FORMAT_VERSION` (currently 2). Pass ``1`` to
            emit a legacy envelope for compatibility with downstream
            tools that haven't been upgraded yet.
        float32_ohlcv: When True, OHLCV float columns are downcast to
            float32 before Parquet encoding (~2x size reduction with
            no observable impact on backtest metrics for typical
            crypto / equity series). Off by default to preserve the
            v1 round-trip contract; opt in for upload / archive
            workflows.

    Returns:
        The final bundle file path.
    """
    if format_version is None:
        format_version = BUNDLE_FORMAT_VERSION
    if format_version not in (1, 2):
        raise ValueError(
            f"Unsupported bundle format_version {format_version}; "
            f"valid values are 1 and 2."
        )

    path = Path(path)
    if path.is_dir():
        name = backtest.algorithm_id or "backtest"
        target = path / f"{name}{BUNDLE_EXT}"
    else:
        target = path if path.suffix == BUNDLE_EXT else path.with_suffix(
            path.suffix + BUNDLE_EXT if path.suffix else BUNDLE_EXT
        )
    target.parent.mkdir(parents=True, exist_ok=True)

    if format_version == 2:
        doc = _build_v2_envelope(backtest)
    else:
        doc = {
            "format_version": 1,
            "backtest": backtest.to_dict(),
        }

    if include_ohlcv and getattr(backtest, "ohlcv", None):
        store = (
            Path(ohlcv_store)
            if ohlcv_store is not None
            else target.parent / "ohlcv"
        )
        manifest = _write_ohlcv_to_store(
            backtest.ohlcv, store, float32=float32_ohlcv
        )
        if manifest:
            try:
                rel_store = os.path.relpath(store, target.parent)
            except ValueError:
                rel_store = str(store)
            doc["ohlcv"] = {
                "store_dir": rel_store,
                "manifest": manifest,
            }

    payload = _encode_payload(doc, format_version=format_version)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, target)
    return target


def open_bundle(
    path: Union[str, Path],
    *,
    ohlcv_store: Optional[Union[str, Path]] = None,
    summary_only: bool = False,
) -> Backtest:
    """Load a :class:`Backtest` from a ``.iafbt`` bundle file.

    Args:
        path: Path to the bundle file.
        ohlcv_store: Override for the OHLCV store directory. Defaults
            to the value persisted in the bundle, resolved relative to
            the bundle's parent directory.
        summary_only: When True (v2 only), skip eager Parquet decode of
            the per-run heavy time series (equity / drawdown / monthly
            / yearly / cumulative_return / rolling_sharpe / TWR
            variants). The blob references are preserved on the run
            dict as opaque ``{"@blob": "<key>"}`` markers; the
            scalar summary metrics (Sharpe, Sortino, max DD, CAGR,
            etc.) are fully populated. Useful for bulk listings /
            ranking pipelines that don't draw charts. Ignored for v1
            bundles, where these series are inline.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Bundle file not found: {path}")

    version, doc = _decode_payload(path.read_bytes())

    if version >= 2:
        blobs = doc.get("blobs") or {}
        engine = doc.get("engine_type")
        runs_key = (
            "vector_runs" if engine == "vector"
            else "event_runs" if engine == "event"
            else "backtest_runs"
        )
        # Always walk the run dicts: when summary_only=True we still
        # need to replace blob references with empty lists so the
        # downstream ``BacktestMetrics.from_dict`` parser doesn't
        # choke on dict values where it expects lists. The Parquet
        # decode is what we actually skip.
        if blobs:
            _resolve_metric_blobs(
                doc, blobs, runs_key=runs_key, summary_only=summary_only
            )
        flat = _envelope_to_backtest_dict(doc)
        backtest = Backtest.from_dict(flat)
    else:
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
