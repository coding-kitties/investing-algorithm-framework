"""SQLite-backed Tier-1 backtest index (epic #540 phase 2).

A :class:`SqliteBacktestIndex` is a single-file SQLite database that
holds one row per backtest bundle, derived from
:class:`BacktestIndexRow`. It is the local-disk implementation of the
Tier-1 store described in
``docs/design/tiered-backtest-storage.md`` \u00a73.1.

Schema
------
The schema is generated from two sources of truth:

* The canonical *identity / provenance / config* columns of
  :class:`BacktestIndexRow`.
* All numeric / string fields of :class:`BacktestSummaryMetrics`,
  promoted as ``summary_<field>`` columns so analysts can filter on
  e.g. ``WHERE summary_sharpe_ratio > 1.0``.

Anything that doesn't fit those is round-tripped opaquely in the
``extras_json`` and ``summary_extras_json`` columns. ``parameters``
and ``strategy_ids`` are stored as JSON text.

The file carries ``PRAGMA user_version = SCHEMA_VERSION`` so future
migrations can detect and upgrade older index files additively.

Concurrency
-----------
Writes go through a single connection in ``WAL`` mode; multiple
readers from other processes are safe.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import (
    Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union,
)

from investing_algorithm_framework.domain.backtesting.backtest_index_row \
    import BacktestIndexRow
from investing_algorithm_framework.domain.backtesting \
    .backtest_summary_metrics import BacktestSummaryMetrics


logger = logging.getLogger(__name__)


# Bumped on any additive schema change. Old files are upgraded
# in-place by :meth:`SqliteBacktestIndex._migrate`.
SCHEMA_VERSION = 2

# Columns of BacktestIndexRow that map 1:1 to typed SQL columns.
# (parameters / strategy_ids are emitted as JSON text columns; the
# scalar metrics are promoted from BacktestSummaryMetrics below.)
_IDENTITY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("bundle_path", "TEXT PRIMARY KEY"),
    ("algorithm_id", "TEXT"),
    ("tag", "TEXT"),
    ("framework_version", "TEXT"),
    ("engine_type", "TEXT"),
    ("risk_free_rate", "REAL"),
    ("number_of_runs", "INTEGER"),
    ("parameters_json", "TEXT"),
    ("strategy_ids_json", "TEXT"),
    ("extras_json", "TEXT"),
    ("summary_extras_json", "TEXT"),
    # Provenance for incremental indexing — skip bundles whose
    # mtime + size match an existing row (epic #540 phase 2).
    ("bundle_mtime_ns", "INTEGER"),
    ("bundle_size", "INTEGER"),
)


def _summary_columns() -> List[Tuple[str, str]]:
    """Promote BacktestSummaryMetrics fields to ``summary_<name>`` cols.

    Numeric fields become ``REAL`` (or ``INTEGER`` if annotated ``int``);
    everything else degrades to ``TEXT``.
    """
    cols: List[Tuple[str, str]] = []
    for f in dc_fields(BacktestSummaryMetrics):
        ann = f.type
        if ann is int or ann == "int":
            sql_type = "INTEGER"
        elif ann is float or ann == "float":
            sql_type = "REAL"
        elif ann is bool or ann == "bool":
            sql_type = "INTEGER"
        else:
            sql_type = "TEXT"
        cols.append((f"summary_{f.name}", sql_type))
    return cols


_SUMMARY_COLUMNS: Tuple[Tuple[str, str], ...] = tuple(_summary_columns())
_SUMMARY_FIELD_NAMES: frozenset = frozenset(
    f.name for f in dc_fields(BacktestSummaryMetrics)
)


def _all_columns() -> List[Tuple[str, str]]:
    return list(_IDENTITY_COLUMNS) + list(_SUMMARY_COLUMNS)


_TABLE = "backtest_index"


class SqliteBacktestIndex:
    """Single-file SQLite index over a directory of ``.iafbt`` bundles.

    Use :meth:`create` to make a fresh file (overwrites if exists),
    :meth:`open` to connect to an existing one (creating tables if
    needed), :meth:`upsert` to add/replace a row, and
    :meth:`iter_rows` / :meth:`query` for read access.
    """

    def __init__(self, path: Union[str, Path], conn: sqlite3.Connection):
        self.path = Path(path)
        self._conn = conn

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, path: Union[str, Path]) -> "SqliteBacktestIndex":
        """Create a fresh index file (overwrites any existing file)."""
        p = Path(path)
        if p.exists():
            p.unlink()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        cls._init_schema(conn)
        return cls(p, conn)

    @classmethod
    def open(cls, path: Union[str, Path]) -> "SqliteBacktestIndex":
        """Open an existing index file, creating tables on first use."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        cls._init_schema(conn)
        cls._migrate(conn)
        return cls(p, conn)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cols = ", ".join(
            f'"{name}" {sql_type}' for name, sql_type in _all_columns()
        )
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{_TABLE}" ({cols})')
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_algorithm_id '
            f'ON "{_TABLE}"(algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_tag '
            f'ON "{_TABLE}"(tag)'
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Additive forward-only migration based on PRAGMA user_version.

        Adds any columns that the current code knows about but the
        on-disk file is missing. Never drops or rewrites existing
        columns.
        """
        existing = {
            row["name"]
            for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')
        }
        for name, sql_type in _all_columns():
            if name not in existing:
                conn.execute(
                    f'ALTER TABLE "{_TABLE}" '
                    f'ADD COLUMN "{name}" {sql_type}'
                )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert(
        self,
        row: BacktestIndexRow,
        bundle_mtime_ns: Optional[int] = None,
        bundle_size: Optional[int] = None,
    ) -> None:
        """Insert or replace a single row, keyed by ``bundle_path``.

        Args:
            row: the typed row to write.
            bundle_mtime_ns: optional file mtime in nanoseconds; used
                by :meth:`is_up_to_date` to support incremental
                indexing (epic #540 phase 2).
            bundle_size: optional file size in bytes, used together
                with ``bundle_mtime_ns`` for the freshness check.

        Raises:
            ValueError: if ``row.bundle_path`` is None (it is the PK).
        """
        if not row.bundle_path:
            raise ValueError(
                "BacktestIndexRow.bundle_path is required for SQLite "
                "upsert (used as the primary key)."
            )
        record = self._row_to_record(row)
        record["bundle_mtime_ns"] = bundle_mtime_ns
        record["bundle_size"] = bundle_size
        cols = list(record.keys())
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(f'"{c}"' for c in cols)
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{_TABLE}" ({col_list}) '
            f'VALUES ({placeholders})',
            [record[c] for c in cols],
        )
        self._conn.commit()

    def is_up_to_date(
        self, bundle_path: str, mtime_ns: int, size: int,
    ) -> bool:
        """Return True if the index already has a row for *bundle_path*
        whose ``(mtime_ns, size)`` matches the on-disk file.

        Used by :func:`build_index` to skip bundles that have not
        changed since the last index build (epic #540 phase 2).
        """
        cur = self._conn.execute(
            f'SELECT bundle_mtime_ns, bundle_size '
            f'FROM "{_TABLE}" WHERE bundle_path = ?',
            (bundle_path,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        return (
            row["bundle_mtime_ns"] == mtime_ns
            and row["bundle_size"] == size
        )

    def upsert_many(self, rows: Iterable[BacktestIndexRow]) -> int:
        """Bulk insert/replace; returns the number of rows written."""
        rows = list(rows)
        if not rows:
            return 0
        # Use the first row to fix the column set; record-builder is
        # deterministic so all rows produce the same keys.
        first = self._row_to_record(rows[0])
        cols = list(first.keys())
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(f'"{c}"' for c in cols)
        sql = (
            f'INSERT OR REPLACE INTO "{_TABLE}" ({col_list}) '
            f'VALUES ({placeholders})'
        )
        payload = [first] + [self._row_to_record(r) for r in rows[1:]]
        for r in payload:
            if not r.get("bundle_path"):
                raise ValueError(
                    "BacktestIndexRow.bundle_path is required for SQLite "
                    "upsert (used as the primary key)."
                )
        self._conn.executemany(sql, [[r[c] for c in cols] for r in payload])
        self._conn.commit()
        return len(rows)

    @staticmethod
    def _row_to_record(row: BacktestIndexRow) -> Dict[str, Any]:
        """Map a typed row onto a flat dict ready for SQL binding."""
        record: Dict[str, Any] = {
            "bundle_path": row.bundle_path,
            "algorithm_id": row.algorithm_id,
            "tag": row.tag,
            "framework_version": row.framework_version,
            "engine_type": row.engine_type,
            "risk_free_rate": row.risk_free_rate,
            "number_of_runs": row.number_of_runs,
            "parameters_json": (
                _safe_json(row.parameters) if row.parameters else None
            ),
            "strategy_ids_json": (
                _safe_json(row.strategy_ids) if row.strategy_ids else None
            ),
            "extras_json": (
                _safe_json(row.extras) if row.extras else None
            ),
        }

        summary_extras: Dict[str, Any] = {}
        if row.summary_metrics is not None:
            summary_dict = row.summary_metrics.to_dict()
            for k, v in summary_dict.items():
                if k in _SUMMARY_FIELD_NAMES:
                    record[f"summary_{k}"] = _coerce_scalar(v)
                else:
                    summary_extras[k] = v

        record["summary_extras_json"] = (
            _safe_json(summary_extras) if summary_extras else None
        )
        return record

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        cur = self._conn.execute(f'SELECT COUNT(*) AS n FROM "{_TABLE}"')
        return int(cur.fetchone()["n"])

    def iter_rows(self) -> Iterator[BacktestIndexRow]:
        """Yield every row as a :class:`BacktestIndexRow`."""
        for sql_row in self._conn.execute(f'SELECT * FROM "{_TABLE}"'):
            yield self._record_to_row(sql_row)

    def query(
        self, where: Optional[str] = None,
        params: Optional[Tuple[Any, ...]] = None,
    ) -> List[BacktestIndexRow]:
        """Run a parameterised ``SELECT`` and return typed rows.

        Args:
            where: optional SQL fragment (without the ``WHERE`` keyword).
            params: positional bind values for ``where``.
        """
        sql = f'SELECT * FROM "{_TABLE}"'
        if where:
            sql += f" WHERE {where}"
        cur = self._conn.execute(sql, params or ())
        return [self._record_to_row(r) for r in cur]

    @staticmethod
    def _record_to_row(sql_row: sqlite3.Row) -> BacktestIndexRow:
        d = dict(sql_row)

        params_json = d.pop("parameters_json", None)
        strat_json = d.pop("strategy_ids_json", None)
        extras_json = d.pop("extras_json", None)
        summary_extras_json = d.pop("summary_extras_json", None)

        summary_dict: Dict[str, Any] = {}
        for name in list(d.keys()):
            if name.startswith("summary_"):
                value = d.pop(name)
                if value is not None:
                    summary_dict[name[len("summary_"):]] = value
        if summary_extras_json:
            try:
                summary_dict.update(json.loads(summary_extras_json))
            except (TypeError, ValueError):
                pass

        kwargs: Dict[str, Any] = {
            "algorithm_id": d.get("algorithm_id"),
            "tag": d.get("tag"),
            "bundle_path": d.get("bundle_path"),
            "framework_version": d.get("framework_version"),
            "engine_type": d.get("engine_type"),
            "risk_free_rate": d.get("risk_free_rate"),
            "number_of_runs": d.get("number_of_runs") or 0,
            "parameters": _safe_loads(params_json) or {},
            "strategy_ids": _safe_loads(strat_json) or [],
            "extras": _safe_loads(extras_json) or {},
            "summary_metrics": (
                BacktestSummaryMetrics.from_dict(summary_dict)
                if summary_dict else None
            ),
        }
        return BacktestIndexRow(**kwargs)

    # ------------------------------------------------------------------
    # House-keeping
    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - best-effort
            pass

    def __enter__(self) -> "SqliteBacktestIndex":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _safe_json(obj: Any) -> Optional[str]:
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return None


def _safe_loads(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _coerce_scalar(v: Any) -> Any:
    """Bind helper: SQLite accepts None / int / float / str / bytes only."""
    if v is None or isinstance(v, (int, float, str, bytes)):
        return v
    if isinstance(v, bool):
        return int(v)
    return str(v)
