"""Single-file binary bundle persistence for :class:`Backtest`.

Implements the bundle format proposed in issue #487, plus the v2
extensions described in ``docs/design/bundle-format-v2.md`` and the
v9.0 dual-engine format described in
``docs/architecture/backtest/v9.0-dual-engine-design.md``.

Format versions
---------------

- **v1** (legacy, read-only): a single zstd-compressed MessagePack
  envelope of ``{"format_version": 1, "backtest": <Backtest.to_dict()>,
  "ohlcv": <optional manifest>}``. Heavy time-series fields live
  inline as lists of ``(value, ISO-string)`` tuples.

- **v2** (legacy, read-only): single-engine envelope. ``engine_type``
  on the top-level dict selects one of ``vector_runs`` /
  ``event_runs`` / ``backtest_runs``; the matching summary metrics
  live under ``vector_metrics`` / ``event_metrics`` /
  ``backtest_summary``. Heavy time series are extracted from each
  ``backtest_metrics`` dict and stored as embedded Parquet bytes
  under a top-level ``blobs`` map keyed
  ``runs/<idx>/metrics/<field>.parquet`` (the prefix does not encode
  the engine — v2 envelopes only ever carry one engine).

- **v3** (legacy, read-only since v9.0+study-extension): dual-engine
  envelope. Both engine slots live side by side as nested dicts under
  the top-level ``vector`` and ``event`` keys; each slot dict carries
  its own ``runs`` / ``summary`` payload. Slots with no data are
  omitted entirely. Heavy-series blob keys are namespaced per engine:
  ``vector_runs/<idx>/metrics/<field>.parquet`` and
  ``event_runs/<idx>/metrics/<field>.parquet``. See design doc \u00a73.

- **v4** (default since study/multi-universe extension): identical
  envelope layout as v3 plus four optional top-level fields
  (``study_name``, ``study_description``, ``universes``) and one
  optional per-engine slot dict key (``summaries_by_universe``).
  Bundles with no universes set degrade to a single-universe shape
  that round-trips with v3 readers (those fields are simply ignored
  by old readers). See ``docs/design/bundle-format-v4.md``.

On read, blob references are resolved back to lists of
``(value, datetime)`` tuples so consumers see the same shape as v1.
``open_bundle(..., summary_only=True)`` skips the Parquet decode
entirely (the references are left in place as opaque dicts), which
keeps bulk-listing fast.

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
from typing import Any, Dict, List, Optional, Tuple, Union

import msgpack
import zstandard as zstd

from .backtest import Backtest, ENGINE_VECTOR, ENGINE_EVENT, ENGINES

logger = logging.getLogger(__name__)


# v9.0 bumped to 3 (dual-engine envelope). The study/multi-universe
# extension bumped to 4 (adds study_name / study_description /
# universes / per-engine summaries_by_universe). Phase 3b bumps to 5
# (multi-study: top-level ``studies`` map keyed by study name, with
# per-study engine slots and namespaced blob keys). Writers always
# emit the current version; readers accept v1, v2, v3, v4 and v5.
BUNDLE_FORMAT_VERSION = 5
BUNDLE_EXT = ".obtf"

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

    v1, v2 and v3 envelopes all share the same outer ``IAFB`` + uint32
    version header and the same zstd-compressed msgpack body \u2014 only
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
# v3 envelope construction / disassembly
# ---------------------------------------------------------------------------


def _extract_metric_blobs(
    run_dicts: List[dict],
    blobs: Dict[str, bytes],
    *,
    key_prefix: str,
) -> None:
    """Walk ``run_dicts`` and replace heavy metric series with
    ``{"@blob": "<key>"}`` references; the actual Parquet bytes are
    appended to *blobs* keyed by
    ``<key_prefix>/<idx>/metrics/<field>.parquet``.

    Mutates the run dicts in place. Fields that aren't recognised
    list-of-tuples shapes are left inline (the encoder is conservative
    by design \u2014 never lose data).

    Args:
        run_dicts: The list of ``BacktestRun.to_dict()`` payloads to
            walk.
        blobs: Output dict; new Parquet bytes are added under the
            namespaced key.
        key_prefix: Engine-namespaced prefix. In v3 this is
            ``"vector_runs"`` or ``"event_runs"``. The legacy v2
            ``"runs"`` prefix is only ever read, never written.
    """
    if not run_dicts:
        return
    for idx, run in enumerate(run_dicts):
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
                # Unrecognised shape \u2014 keep inline as v1 fallback.
                continue
            key = f"{key_prefix}/{idx}/metrics/{field}.parquet"
            blobs[key] = payload
            metrics[field] = {_BLOB_REF_KEY: key}


def _resolve_metric_blobs(
    run_dicts: List[dict],
    blobs: Dict[str, bytes],
    *,
    summary_only: bool = False,
) -> None:
    """Inverse of :func:`_extract_metric_blobs`: walk ``run_dicts``
    and replace any ``{"@blob": "<key>"}`` reference with the decoded
    series. The blob key is taken verbatim from the reference dict,
    so this works for both v2 (``runs/<idx>/...``) and v3
    (``vector_runs/<idx>/...`` / ``event_runs/<idx>/...``) layouts.

    When ``summary_only=True``, references are replaced with empty
    lists instead of being decoded \u2014 this keeps the
    ``BacktestMetrics.from_dict`` contract (it expects lists for
    these fields, not refs) while skipping the Parquet decode cost.
    The scalar summary fields (sharpe / sortino / max_dd / etc.)
    on the same metrics object remain fully populated, which is the
    whole point of this mode.
    """
    if not run_dicts:
        return
    for run in run_dicts:
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


def _build_v4_envelope(backtest: Backtest) -> dict:
    """Build the on-disk ``doc`` dict for a v4 bundle from *backtest*.

    The layout is a strict superset of v3: same per-engine ``vector`` /
    ``event`` slot dicts, same per-engine blob namespacing, plus four
    optional top-level study/universe keys and a per-engine
    ``summaries_by_universe`` dict. v3 readers ignore the new keys and
    still get a valid single-universe view.
    """
    blobs: Dict[str, bytes] = {}
    envelope: Dict[str, Any] = {
        "format_version": BUNDLE_FORMAT_VERSION,
        "algorithm_id": backtest.algorithm_id,
        "tag": backtest.tag,
        "risk_free_rate": backtest.risk_free_rate,
        "strategy_ids": list(backtest.strategy_ids or []),
        "parameters": dict(backtest.parameters or {}),
        "metadata": dict(backtest.metadata or {}),
        "monte_carlo_tests": [
            pt.to_dict() for pt in backtest.backtest_monte_carlo_tests
        ] if backtest.backtest_monte_carlo_tests else None,
        # v4 study / multi-universe extension. Always emitted (even
        # when empty) so the reader can distinguish "explicitly empty"
        # from "absent" without ambiguity. Empty list / dict / None
        # payloads stay cheap on the wire.
        "study_name": (_ds.name if (_ds := backtest.get_study()) else None),
        "study_description": (_ds.description if (_ds := backtest.get_study()) else None),
        "universes": [
            u.to_dict() for u in (backtest.universes or [])
        ],
    }

    for engine in ENGINES:
        runs = backtest.get_runs(engine)
        summary = backtest.get_summary(engine)
        per_universe = (
            backtest.vector_summaries_by_universe
            if engine == ENGINE_VECTOR
            else backtest.event_summaries_by_universe
        ) or {}
        # Emit the slot when *any* engine-scoped content exists \u2014 runs,
        # a pooled summary, or per-universe summaries. v3 only checked
        # ``runs``; under v4 a bundle can legitimately carry only
        # per-universe summaries (e.g. when runs were dropped to make
        # a summary-only archive) so we widen the predicate.
        if not runs and summary is None and not per_universe:
            continue
        run_dicts = [br.to_dict() for br in runs] if runs else []
        if run_dicts:
            _extract_metric_blobs(
                run_dicts, blobs, key_prefix=f"{engine}_runs",
            )
        slot: Dict[str, Any] = {
            "runs": run_dicts,
            "summary": summary.to_dict() if summary else None,
        }
        if per_universe:
            slot["summaries_by_universe"] = {
                k: v.to_dict()
                for k, v in per_universe.items()
                if v is not None
            }
        envelope[engine] = slot

    if blobs:
        envelope["blobs"] = blobs
    return envelope


# Backwards-compatible alias retained for any external callers that
# imported the pre-v4 helper. The v4 envelope is a strict superset of
# v3 so the previous name still produces a valid on-disk doc.
_build_v3_envelope = _build_v4_envelope


# ---------------------------------------------------------------------------
# v5 envelope: multi-study top-level ``studies`` map
# ---------------------------------------------------------------------------


def _build_v5_envelope(backtest: Backtest) -> dict:
    """Build the on-disk ``doc`` dict for a v5 bundle.

    The envelope IS the ``Backtest.to_dict()`` shape plus a
    ``format_version`` discriminator and optional ``blobs`` map.
    Everything lives inside the ``studies`` dict; there are no
    redundant top-level study/universe/risk-free-rate keys.

    Blob keys follow the per-study namespacing:
    ``studies/<study_name>/<engine>_runs/<idx>/metrics/<field>.parquet``
    """
    blobs: Dict[str, bytes] = {}
    envelope: Dict[str, Any] = backtest.to_dict()
    envelope["format_version"] = BUNDLE_FORMAT_VERSION

    # Extract heavy metric series into Parquet blobs, updating the
    # run dicts in-place with blob references.
    for name in list(envelope.get("studies") or {}):
        study_dict = envelope["studies"][name]
        for runs_key in ("vector_runs", "event_runs"):
            run_dicts = study_dict.get(runs_key) or []
            if run_dicts:
                engine = runs_key.replace("_runs", "")
                _extract_metric_blobs(
                    run_dicts,
                    blobs,
                    key_prefix=f"studies/{name}/{engine}_runs",
                )

    if blobs:
        envelope["blobs"] = blobs
    return envelope


def _v5_envelope_to_backtest(doc: dict) -> Backtest:
    """Reconstruct a :class:`Backtest` from a v5 envelope.

    The v5 envelope is the ``Backtest.to_dict()`` shape, so we can
    delegate directly to ``Backtest.from_dict`` — no intermediate
    flat-dict conversion needed.
    """
    return Backtest.from_dict(doc)


def _resolve_v5_metric_blobs(
    studies_raw: Dict[str, dict],
    blobs: Dict[str, bytes],
    *,
    summary_only: bool = False,
) -> None:
    """v5 inverse of :func:`_extract_metric_blobs`. Walks every
    study's per-engine run lists and resolves blob references in
    place. Blob keys follow the v5 namespacing
    ``studies/<study>/<engine>_runs/<idx>/metrics/<field>.parquet``;
    however the resolver reads the key verbatim from the reference
    dict, so it is layout-agnostic.
    """
    if not studies_raw:
        return
    for study_raw in studies_raw.values():
        for runs_key in ("vector_runs", "event_runs"):
            run_dicts = (study_raw or {}).get(runs_key) or []
            _resolve_metric_blobs(
                run_dicts, blobs, summary_only=summary_only,
            )


def _envelope_to_backtest_dict(doc: dict, version: int) -> dict:
    """Collapse an on-disk envelope back into the v9.0 canonical dict
    shape consumed by :py:meth:`Backtest.from_dict`.

    Dispatches on ``version``:

    * v3 \u2014 read the ``vector`` / ``event`` slot dicts directly.
    * v2 \u2014 read ``vector_runs`` / ``event_runs`` / ``backtest_runs``
      (whichever the envelope's ``engine_type`` selected), route into
      the matching v9.0 engine slot. ``engine_type is None`` defaults
      to vector (design doc \u00a72.6.1).
    """
    if version >= 3:
        vector_slot = doc.get("vector") or {}
        event_slot = doc.get("event") or {}
        return {
            "algorithm_id": doc.get("algorithm_id"),
            "vector_runs": vector_slot.get("runs"),
            "vector_summary": vector_slot.get("summary"),
            "event_runs": event_slot.get("runs"),
            "event_summary": event_slot.get("summary"),
            "backtest_monte_carlo_tests":
                doc.get("monte_carlo_tests"),
            "metadata": doc.get("metadata") or {},
            "risk_free_rate": doc.get("risk_free_rate"),
            "strategy_ids": doc.get("strategy_ids") or [],
            "parameters": doc.get("parameters") or {},
            "tag": doc.get("tag"),
            # v4 fields. Absent on v3 envelopes; ``.get`` keeps the
            # default empty list / dict / None so old bundles flow
            # through unchanged.
            "study_name": doc.get("study_name"),
            "study_description": doc.get("study_description"),
            "universes": doc.get("universes") or [],
            "vector_summaries_by_universe":
                vector_slot.get("summaries_by_universe") or {},
            "event_summaries_by_universe":
                event_slot.get("summaries_by_universe") or {},
        }

    # v2 legacy.
    engine = doc.get("engine_type")
    if engine == ENGINE_EVENT:
        runs_key, metrics_key = "event_runs", "event_metrics"
        target = ENGINE_EVENT
    elif engine == ENGINE_VECTOR:
        runs_key, metrics_key = "vector_runs", "vector_metrics"
        target = ENGINE_VECTOR
    else:
        # Engine-agnostic legacy bundle. Default to vector.
        runs_key, metrics_key = "backtest_runs", "backtest_summary"
        target = ENGINE_VECTOR

    legacy_runs = doc.get(runs_key)
    legacy_summary = doc.get(metrics_key)
    out: Dict[str, Any] = {
        "algorithm_id": doc.get("algorithm_id"),
        "vector_runs": None,
        "vector_summary": None,
        "event_runs": None,
        "event_summary": None,
        "backtest_monte_carlo_tests":
            doc.get("backtest_monte_carlo_tests"),
        "metadata": doc.get("metadata") or {},
        "risk_free_rate": doc.get("risk_free_rate"),
        "strategy_ids": doc.get("strategy_ids") or [],
        "parameters": doc.get("parameters") or {},
        "tag": doc.get("tag"),
    }
    if target == ENGINE_VECTOR:
        out["vector_runs"] = legacy_runs
        out["vector_summary"] = legacy_summary
    else:
        out["event_runs"] = legacy_runs
        out["event_summary"] = legacy_summary
    return out


def _merge_v3_envelopes(
    new_doc: Dict[str, Any], old_doc: Dict[str, Any]
) -> None:
    """Merge engine slots from ``old_doc`` into ``new_doc`` in place.

    Implements the merge-on-save rule from design doc \u00a73.5:

    * For each engine in :data:`ENGINES`, if ``new_doc`` does not carry
      a slot for that engine (i.e. the in-memory backtest had no runs
      for it), the on-disk slot and its namespaced blobs
      (``<engine>_runs/...``) are preserved.
    * Engines present in ``new_doc`` replace the on-disk slot entirely,
      together with any blobs under their namespace.

    Top-level fields (``algorithm_id``, ``tag``, ``metadata`` etc.)
    are owned by the in-memory backtest and are not merged.
    """
    new_blobs = dict(new_doc.get("blobs") or {})
    old_blobs = old_doc.get("blobs") or {}
    for engine in ENGINES:
        if engine in new_doc:
            continue  # in-memory replaces the on-disk slot
        old_slot = old_doc.get(engine)
        if not isinstance(old_slot, dict):
            continue
        new_doc[engine] = old_slot
        prefix = f"{engine}_runs/"
        for k, v in old_blobs.items():
            if k.startswith(prefix):
                new_blobs[k] = v
    if new_blobs:
        new_doc["blobs"] = new_blobs


def _load_existing_envelope_for_merge(
    target: Path,
) -> Optional[Dict[str, Any]]:
    """Read ``target`` and return a v3 envelope suitable for merging.

    Returns ``None`` if the target does not exist, is not a valid
    bundle, or fails to decode. v1 / v2 bundles are upgraded in
    memory to the v3 envelope shape (via :func:`open_bundle` +
    :func:`_build_v3_envelope`) so the caller can use a single merge
    code path.
    """
    if not target.is_file():
        return None
    try:
        blob = target.read_bytes()
    except OSError:
        return None
    if not blob.startswith(_MAGIC):
        return None
    try:
        version, existing_doc = _decode_payload(blob)
    except Exception:  # pragma: no cover - corrupted file
        logger.warning(
            "Existing bundle at %s could not be decoded; "
            "overwriting without merge.", target,
        )
        return None
    if version >= 3:
        return existing_doc
    # v1 / v2: load via open_bundle and rebuild as a v3 envelope so the
    # merge logic is uniform.
    try:
        existing_bt = open_bundle(target)
    except Exception:  # pragma: no cover - corrupted legacy file
        logger.warning(
            "Legacy bundle at %s could not be re-materialised for "
            "merge-on-save; overwriting.", target,
        )
        return None
    return _build_v3_envelope(existing_bt)


def _merge_v5_envelopes(
    new_doc: Dict[str, Any], old_doc: Dict[str, Any]
) -> None:
    """Merge studies from ``old_doc`` into ``new_doc`` in place.

    v5 generalisation of :func:`_merge_v3_envelopes`. Two rules:

    1. **Disjoint studies** — any study present on disk but absent
       from the in-memory backtest is preserved verbatim, along with
       its blobs (``studies/<name>/...``).
    2. **Same-name studies** — for studies present on both sides,
       merge their engine slots: the in-memory engine wins when
       populated, otherwise the on-disk engine is preserved. This
       keeps the v3/v4 invariant that saving an event-only backtest
       over a vector-only bundle yields a bundle with both engines.

    This realises the "concurrent writers serialise on the header
    rewrite, otherwise touch disjoint study slots" semantics from
    the multi-study design doc §3.4 — without yet introducing the
    portalocker dance (deferred to Phase 3b.2).
    """
    new_studies = new_doc.get("studies") or {}
    old_studies = old_doc.get("studies") or {}
    new_blobs = dict(new_doc.get("blobs") or {})
    old_blobs = old_doc.get("blobs") or {}

    for name, old_study in old_studies.items():
        if name not in new_studies:
            # Rule 1: copy disjoint study + its blobs.
            new_studies[name] = old_study
            prefix = f"studies/{name}/"
            for k, v in old_blobs.items():
                if k.startswith(prefix):
                    new_blobs[k] = v
            continue

        # Rule 2: merge engine slots within the same-named study
        # (flat v9.0 format: vector_runs / event_runs / ... keys).
        new_study = new_studies[name]
        for engine in ("vector", "event"):
            runs_key = f"{engine}_runs"
            summary_key = f"{engine}_summary"
            sbu_key = f"{engine}_summaries_by_universe"
            new_has_engine = bool(
                new_study.get(runs_key)
                or new_study.get(summary_key)
                or new_study.get(sbu_key)
            )
            old_study_raw = old_studies[name] or {}
            old_has_engine = bool(
                old_study_raw.get(runs_key)
                or old_study_raw.get(summary_key)
                or old_study_raw.get(sbu_key)
            )
            if new_has_engine or not old_has_engine:
                continue
            # Carry over the on-disk engine data.
            new_study[runs_key] = old_study_raw.get(runs_key)
            new_study[summary_key] = old_study_raw.get(summary_key)
            new_study[sbu_key] = old_study_raw.get(sbu_key)
            prefix = f"studies/{name}/{engine}_runs/"
            for k, v in old_blobs.items():
                if k.startswith(prefix):
                    new_blobs[k] = v

    new_doc["studies"] = new_studies
    if new_blobs:
        new_doc["blobs"] = new_blobs


def _load_existing_v5_envelope_for_merge(
    target: Path,
) -> Optional[Dict[str, Any]]:
    """Read ``target`` and return a v5 envelope suitable for merging.

    Returns ``None`` if the target does not exist, isn't a valid
    bundle, or fails to decode. v1–v4 bundles are upgraded in memory
    to the v5 envelope shape (via :func:`open_bundle` +
    :func:`_build_v5_envelope`) so the merger can use one code path.
    """
    if not target.is_file():
        return None
    try:
        blob = target.read_bytes()
    except OSError:
        return None
    if not blob.startswith(_MAGIC):
        return None
    try:
        version, existing_doc = _decode_payload(blob)
    except Exception:  # pragma: no cover - corrupted file
        logger.warning(
            "Existing bundle at %s could not be decoded; "
            "overwriting without merge.", target,
        )
        return None
    if version >= 5:
        return existing_doc
    # v1–v4: rehydrate via the public reader and rebuild as v5.
    try:
        existing_bt = open_bundle(target)
    except Exception:  # pragma: no cover - corrupted legacy file
        logger.warning(
            "Legacy bundle at %s could not be re-materialised for "
            "merge-on-save; overwriting.", target,
        )
        return None
    return _build_v5_envelope(existing_bt)


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    """Atomically write *payload* to *target*.

    Writes to ``<target>.tmp.<pid>``, ``fsync``s the temp file,
    ``os.replace``s it over the target, then ``fsync``s the parent
    directory. Matches the v2 writer's atomicity guarantees (design
    doc \u00a73.5).
    """
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    with open(tmp, "wb") as f:
        f.write(payload)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:  # pragma: no cover - rare fs without fsync
            pass
    os.replace(tmp, target)
    try:
        dir_fd = os.open(target.parent, os.O_RDONLY)
    except OSError:  # pragma: no cover - dir fsync unsupported
        return
    try:
        try:
            os.fsync(dir_fd)
        except OSError:  # pragma: no cover - e.g. Windows
            pass
    finally:
        os.close(dir_fd)


def save_bundle(
    backtest: Backtest,
    path: Union[str, Path],
    *,
    include_ohlcv: bool = False,
    ohlcv_store: Optional[Union[str, Path]] = None,
    format_version: Optional[int] = None,
    float32_ohlcv: bool = False,
    merge: bool = True,
) -> Path:
    """Write *backtest* to a single ``.obtf`` bundle.

    Args:
        backtest: The :class:`Backtest` to persist.
        path: Destination path. If it is a directory, the file is
            written as ``<path>/<algorithm_id_or_hash>.obtf``.
            Otherwise the path is used as-is (with ``.obtf`` appended
            if the suffix is missing).
        include_ohlcv: When True, OHLCV blobs attached to
            ``backtest.ohlcv`` are written to ``ohlcv_store`` (defaulting
            to a sibling ``ohlcv/`` directory next to the bundle) using
            content-addressed Parquet, and a manifest is embedded in
            the bundle.
        ohlcv_store: Override for the OHLCV store directory. Useful
            when persisting many bundles to share a single store.
        format_version: Force a specific bundle format. Defaults to
            :data:`BUNDLE_FORMAT_VERSION` (currently 3). v9.0 only
            writes v3; passing ``1`` or ``2`` raises ``ValueError``.
            The parameter is retained for forward compatibility.
        float32_ohlcv: When True, OHLCV float columns are downcast to
            float32 before Parquet encoding (~2x size reduction with
            no observable impact on backtest metrics for typical
            crypto / equity series). Off by default to preserve the
            v1 round-trip contract; opt in for upload / archive
            workflows.
        merge: When True (default), if the target file already exists
            the writer merges per design doc \u00a73.5: any engine slot
            absent from *backtest* preserves the on-disk slot and its
            blobs. When False the target is overwritten unconditionally
            (legacy v8 semantics). Existing v1 / v2 bundles are
            upgraded to v3 in the process either way.

    Returns:
        The final bundle file path.
    """
    if format_version is None:
        format_version = BUNDLE_FORMAT_VERSION
    if format_version != BUNDLE_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported bundle format_version {format_version}; "
            f"this version of investing_algorithm_framework only "
            f"writes v{BUNDLE_FORMAT_VERSION} bundles. Legacy archives "
            f"are still readable via `open_bundle()` / `Backtest.open()`."
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

    doc = _build_v5_envelope(backtest)

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

    if merge:
        existing = _load_existing_v5_envelope_for_merge(target)
        if existing is not None:
            _merge_v5_envelopes(doc, existing)

    payload = _encode_payload(doc, format_version=format_version)
    _atomic_write_bytes(target, payload)
    return target


def remove_study_from_bundle(
    path: Union[str, Path],
    study_name: str,
) -> bool:
    """Remove a named study slot (and all its blobs) from a bundle in place.

    The file is rewritten atomically.  All other studies, blobs, and
    top-level fields are preserved.

    Args:
        path: Path to the ``.obtf`` bundle file.
        study_name: Name of the study to remove (as it appears under the
            ``studies`` key in the envelope, e.g.
            ``"time_oos_param_sweep"``).

    Returns:
        ``True`` if the study was found and removed, ``False`` if the
        bundle did not contain a study with that name (file is untouched).

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file is not a valid ``.obtf`` bundle.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Bundle not found: {path}")

    blob = path.read_bytes()
    if not blob.startswith(_MAGIC):
        raise ValueError(f"Not a valid .obtf bundle (missing IAFB magic): {path}")

    version, doc = _decode_payload(blob)

    # For legacy v1–v4 bundles upgrade to the v5 envelope shape first
    # so we always work on the ``studies`` dict.
    if version < 5:
        try:
            bt = open_bundle(path)
            doc = _build_v5_envelope(bt)
        except Exception as exc:
            raise ValueError(
                f"Could not decode legacy bundle for study removal: {exc}"
            ) from exc

    studies = doc.get("studies") or {}
    if study_name not in studies:
        return False

    # Remove the study's blob data (keyed ``studies/<name>/...``).
    prefix = f"studies/{study_name}/"
    blobs = doc.get("blobs") or {}
    doc["blobs"] = {k: v for k, v in blobs.items() if not k.startswith(prefix)}

    # Remove the study slot itself.
    del studies[study_name]
    doc["studies"] = studies

    payload = _encode_payload(doc, format_version=BUNDLE_FORMAT_VERSION)
    _atomic_write_bytes(path, payload)
    return True


def open_bundle(
    path: Union[str, Path],
    *,
    ohlcv_store: Optional[Union[str, Path]] = None,
    summary_only: bool = False,
) -> Backtest:
    """Load a :class:`Backtest` from a ``.obtf`` bundle file.

    Args:
        path: Path to the bundle file.
        ohlcv_store: Override for the OHLCV store directory. Defaults
            to the value persisted in the bundle, resolved relative to
            the bundle's parent directory.
        summary_only: When True (v2/v3 only), skip eager Parquet decode
            of the per-run heavy time series (equity / drawdown /
            monthly / yearly / cumulative_return / rolling_sharpe /
            TWR variants). The blob references are preserved on the
            run dict as opaque ``{"@blob": "<key>"}`` markers; the
            scalar summary metrics (Sharpe, Sortino, max DD, CAGR,
            etc.) are fully populated. Useful for bulk listings /
            ranking pipelines that don't draw charts. Ignored for v1
            bundles, where these series are inline.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Bundle file not found: {path}")

    version, doc = _decode_payload(path.read_bytes())

    if version >= 5:
        # v5: top-level ``studies`` map. Resolve blobs across all
        # studies, then split into legacy + extras.
        blobs = doc.get("blobs") or {}
        studies_raw = doc.get("studies") or {}
        _resolve_v5_metric_blobs(
            studies_raw, blobs, summary_only=summary_only,
        )
        backtest = _v5_envelope_to_backtest(doc)
    elif version >= 2:
        blobs = doc.get("blobs") or {}
        if version >= 3:
            # v3 / v4: walk both engine slots' run lists.
            for engine in ENGINES:
                slot = doc.get(engine)
                if not isinstance(slot, dict):
                    continue
                _resolve_metric_blobs(
                    slot.get("runs") or [],
                    blobs,
                    summary_only=summary_only,
                )
        else:
            # v2: single engine slot, dispatched via ``engine_type``.
            engine = doc.get("engine_type")
            runs_key = (
                "vector_runs" if engine == ENGINE_VECTOR
                else "event_runs" if engine == ENGINE_EVENT
                else "backtest_runs"
            )
            _resolve_metric_blobs(
                doc.get(runs_key) or [],
                blobs,
                summary_only=summary_only,
            )
        flat = _envelope_to_backtest_dict(doc, version)
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


def migrate_v2_to_v5(path: Union[str, Path]) -> Path:
    """In-place migration of any pre-v5 ``.obtf`` bundle to v5.

    Reads *path* via :func:`open_bundle` (which transparently handles
    v1 / v2 / v3 / v4 envelopes), then rewrites the file as v5 via
    :func:`save_bundle`. Round-trip is lossless: pre-v5 bundles are
    single-study, so the migrator emits exactly one entry in the v5
    ``studies`` map keyed by ``backtest.study_name or "default"``.

    The function name keeps the historical "v2" tag for callers that
    follow the design doc §9 naming (``migrate_v2_to_v5``); it
    accepts *any* version below v5.

    Args:
        path: Path to the bundle to migrate.

    Returns:
        The same path (rewritten in-place at v5).

    Raises:
        FileNotFoundError: If the bundle does not exist.
        ValueError: If the bundle is not a valid IAF bundle.
    """
    path = Path(path)
    current = peek_bundle_format_version(path)
    if current is None:
        raise ValueError(f"Not a valid IAF bundle: {path}")
    if current >= BUNDLE_FORMAT_VERSION:
        return path  # already at target
    backtest = open_bundle(path)
    save_bundle(backtest, path, merge=False)
    return path


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


def peek_bundle_format_version(path: Union[str, Path]) -> Optional[int]:
    """Return the bundle's ``format_version`` without decoding the body.

    Reads only the 8-byte header (4-byte magic + uint32 LE version).
    Returns ``None`` when *path* is not a readable bundle file. Used
    to cheaply check a bundle's on-disk version without a full decode
    (e.g. before deciding whether a merge-on-save needs to upgrade it).
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        with open(p, "rb") as fh:
            header = fh.read(8)
    except OSError:
        return None
    if len(header) < 8 or header[:4] != _MAGIC:
        return None
    return int.from_bytes(header[4:8], "little")


# Public re-export for convenience.
__all__ = [
    "BUNDLE_EXT",
    "BUNDLE_FORMAT_VERSION",
    "LazyOhlcvDict",
    "is_bundle_file",
    "migrate_v2_to_v5",
    "open_bundle",
    "peek_bundle_format_version",
    "save_bundle",
]
