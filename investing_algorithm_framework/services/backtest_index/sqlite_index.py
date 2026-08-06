"""SQLite-backed Tier-1 backtest index (epic #540 phase 2).

A :class:`SqliteBacktestIndex` is a single-file SQLite database that
holds one row per backtest bundle, derived from
:class:`BacktestIndexRow`. It is the local-disk implementation of the
Tier-1 store described in
``docs/architecture/backtest/tiered-backtest-storage.md`` \u00a73.1.

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
#
# v3 (v9.0): composite primary key ``(bundle_path, engine_type)`` so a
# single dual-engine bundle can carry two rows — one per engine —
# without colliding. ``engine_type`` is now NOT NULL with a default of
# ``'vector'`` to keep the composite PK well-defined for legacy data.
# v4 (multi-universe / studies): adds ``universe_key`` /
# ``study_name`` / ``study_description`` columns and extends the
# composite PK to ``(bundle_path, engine_type, universe_key)`` so a
# single bundle can carry one pooled row per engine *plus* one row
# per (engine, universe). The pooled row stores ``universe_key=''``
# at the SQL level (mapped to/from ``None`` at the typed-row
# boundary) because SQLite treats NULLs in composite primary keys
# as distinct, which would defeat the upsert contract.
# v5 (Phase 3d — multi-study runner): extends the composite PK to
# ``(bundle_path, engine_type, universe_key, study_name)`` so a
# single bundle can carry one row set per study (each study having
# its own per-engine and per-(engine, universe) rows). Legacy rows
# with ``study_name IS NULL`` are coerced to ``'default'`` — the
# canonical sentinel for the unnamed default study (see
# ``docs/design/multi-study-bundle.md`` §4.3).
SCHEMA_VERSION = 5

# Columns of BacktestIndexRow that map 1:1 to typed SQL columns.
# (parameters / strategy_ids are emitted as JSON text columns; the
# scalar metrics are promoted from BacktestSummaryMetrics below.)
#
# The composite primary key
# ``(bundle_path, engine_type, universe_key)`` is emitted as a
# separate ``PRIMARY KEY (...)`` table constraint in
# :meth:`SqliteBacktestIndex._init_schema`, so the listed columns
# carry no per-column ``PRIMARY KEY`` modifier here.
_IDENTITY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("bundle_path", "TEXT NOT NULL"),
    ("algorithm_id", "TEXT"),
    # Optional lineage pointer used by ``rank_index(
    # anchor_algorithm_id=...)`` to pull a champion's whole
    # sibling-bundle neighbourhood (param-robustness, cooldown
    # stress, ...) in one SQL hop. ``NULL`` on anchor bundles. v5+.
    ("anchor_algorithm_id", "TEXT"),
    ("tag", "TEXT"),
    ("framework_version", "TEXT"),
    ("engine_type", "TEXT NOT NULL DEFAULT 'vector'"),
    ("universe_key", "TEXT NOT NULL DEFAULT ''"),
    ("study_name", "TEXT NOT NULL DEFAULT 'default'"),
    ("study_description", "TEXT"),
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
    """Single-file SQLite index over a directory of ``.obtf`` bundles.

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
        """Create the table on first use, leaving existing tables alone.

        ``PRAGMA user_version`` is only stamped when this method
        actually creates the table; otherwise it is left for
        :meth:`_migrate` to read and update.
        """
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (_TABLE,),
        ).fetchone()
        if existing is None:
            cols = ", ".join(
                f'"{name}" {sql_type}' for name, sql_type in _all_columns()
            )
            conn.execute(
                f'CREATE TABLE "{_TABLE}" ({cols}, '
                f'PRIMARY KEY ("bundle_path", "engine_type", '
                f'"universe_key", "study_name"))'
            )
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_algorithm_id '
                f'ON "{_TABLE}"(algorithm_id)'
            )
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS '
                f'idx_{_TABLE}_anchor_algorithm_id '
                f'ON "{_TABLE}"(anchor_algorithm_id)'
            )
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_tag '
                f'ON "{_TABLE}"(tag)'
            )
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Forward-only migration based on ``PRAGMA user_version``.

        * ``< 3``: rebuild the table with the v9.0 composite primary
          key ``(bundle_path, engine_type)``; legacy rows whose
          ``engine_type`` is NULL are coerced to ``'vector'`` per
          design doc §2.6.1 / §5.
        * ``< 4``: extend the composite primary key to include
          ``universe_key`` (defaulted to ``''`` for legacy rows) and
          add the ``study_name`` / ``study_description`` columns.
        * ``< 5``: extend the composite primary key to include
          ``study_name`` (defaulted to ``'default'`` for legacy rows)
          so a single bundle can carry one row set per study slot.
        * Then add any columns that the current code knows about but
          the on-disk file is missing (additive, never drops).
        """
        cur_version = int(
            conn.execute("PRAGMA user_version").fetchone()[0]
        )
        if cur_version < 3:
            SqliteBacktestIndex._migrate_to_v3(conn)
            cur_version = 3
        if cur_version < 4:
            SqliteBacktestIndex._migrate_to_v4(conn)
            cur_version = 4
        if cur_version < 5:
            SqliteBacktestIndex._migrate_to_v5(conn)

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

    @staticmethod
    def _migrate_to_v3(conn: sqlite3.Connection) -> None:
        """Rebuild the table with the composite PK introduced in v9.0.

        SQLite does not support changing a table's primary key in
        place, so we create a sibling table with the new schema,
        copy rows across (defaulting ``engine_type`` to ``'vector'``
        when NULL), drop the original, and rename the new table into
        position. The migration is idempotent: a no-op when no rows
        exist or when the table already declares the composite PK.
        """
        old_cols = [
            row["name"]
            for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')
        ]
        if not old_cols:
            return  # fresh DB — _init_schema will set things up

        tmp_table = f"{_TABLE}__v3_tmp"
        new_cols_sql = ", ".join(
            f'"{name}" {sql_type}' for name, sql_type in _all_columns()
        )
        conn.execute(
            f'CREATE TABLE "{tmp_table}" ({new_cols_sql}, '
            f'PRIMARY KEY ("bundle_path", "engine_type"))'
        )

        # Carry over the intersection of old/new columns; coerce NULL
        # engine_type to 'vector' so the composite PK is well-defined.
        new_col_names = [name for name, _ in _all_columns()]
        shared = [c for c in old_cols if c in new_col_names]
        select_exprs = [
            ("COALESCE(\"engine_type\", 'vector')"
             if c == "engine_type" else f'"{c}"')
            for c in shared
        ]
        insert_cols = ", ".join(f'"{c}"' for c in shared)
        conn.execute(
            f'INSERT OR IGNORE INTO "{tmp_table}" ({insert_cols}) '
            f'SELECT {", ".join(select_exprs)} FROM "{_TABLE}"'
        )

        conn.execute(f'DROP TABLE "{_TABLE}"')
        conn.execute(
            f'ALTER TABLE "{tmp_table}" RENAME TO "{_TABLE}"'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_algorithm_id '
            f'ON "{_TABLE}"(algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS '
            f'idx_{_TABLE}_anchor_algorithm_id '
            f'ON "{_TABLE}"(anchor_algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_tag '
            f'ON "{_TABLE}"(tag)'
        )

    @staticmethod
    def _migrate_to_v4(conn: sqlite3.Connection) -> None:
        """Rebuild the table with the v4 composite primary key
        ``(bundle_path, engine_type, universe_key)`` and add the
        ``study_name`` / ``study_description`` columns.

        Pre-existing rows are pooled rows by definition (no
        per-universe summaries existed before v4), so they get
        ``universe_key=''`` — the SQL-level sentinel for the pooled
        cross-universe row. The migration is idempotent: a no-op
        when no rows exist.
        """
        old_cols = [
            row["name"]
            for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')
        ]
        if not old_cols:
            return

        tmp_table = f"{_TABLE}__v4_tmp"
        new_cols_sql = ", ".join(
            f'"{name}" {sql_type}' for name, sql_type in _all_columns()
        )
        conn.execute(
            f'CREATE TABLE "{tmp_table}" ({new_cols_sql}, '
            f'PRIMARY KEY ("bundle_path", "engine_type", '
            f'"universe_key"))'
        )

        # Copy over the intersection of old/new columns; legacy rows
        # are pooled rows so universe_key defaults to '' via the
        # column DEFAULT clause when not present in the source.
        new_col_names = [name for name, _ in _all_columns()]
        shared = [c for c in old_cols if c in new_col_names]
        select_exprs = [
            ("COALESCE(\"universe_key\", '')"
             if c == "universe_key" else f'"{c}"')
            for c in shared
        ]
        insert_cols = ", ".join(f'"{c}"' for c in shared)
        conn.execute(
            f'INSERT OR IGNORE INTO "{tmp_table}" ({insert_cols}) '
            f'SELECT {", ".join(select_exprs)} FROM "{_TABLE}"'
        )

        conn.execute(f'DROP TABLE "{_TABLE}"')
        conn.execute(
            f'ALTER TABLE "{tmp_table}" RENAME TO "{_TABLE}"'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_algorithm_id '
            f'ON "{_TABLE}"(algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS '
            f'idx_{_TABLE}_anchor_algorithm_id '
            f'ON "{_TABLE}"(anchor_algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_tag '
            f'ON "{_TABLE}"(tag)'
        )

    @staticmethod
    def _migrate_to_v5(conn: sqlite3.Connection) -> None:
        """Rebuild the table with the v5 composite primary key
        ``(bundle_path, engine_type, universe_key, study_name)`` so a
        single bundle can carry one row set per study slot (Phase 3d
        of ``docs/design/multi-study-bundle.md``).

        Pre-existing rows had no notion of ``study_name`` (or carried
        it as a NULL/free-form string) — they are coerced to the
        canonical ``'default'`` sentinel so the composite primary key
        stays well-defined for legacy data. The migration is
        idempotent: a no-op when no rows exist.
        """
        old_cols = [
            row["name"]
            for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')
        ]
        if not old_cols:
            return

        tmp_table = f"{_TABLE}__v5_tmp"
        new_cols_sql = ", ".join(
            f'"{name}" {sql_type}' for name, sql_type in _all_columns()
        )
        conn.execute(
            f'CREATE TABLE "{tmp_table}" ({new_cols_sql}, '
            f'PRIMARY KEY ("bundle_path", "engine_type", '
            f'"universe_key", "study_name"))'
        )

        new_col_names = [name for name, _ in _all_columns()]
        shared = [c for c in old_cols if c in new_col_names]
        select_exprs = [
            ("COALESCE(NULLIF(\"study_name\", ''), 'default')"
             if c == "study_name" else f'"{c}"')
            for c in shared
        ]
        insert_cols = ", ".join(f'"{c}"' for c in shared)
        conn.execute(
            f'INSERT OR IGNORE INTO "{tmp_table}" ({insert_cols}) '
            f'SELECT {", ".join(select_exprs)} FROM "{_TABLE}"'
        )

        conn.execute(f'DROP TABLE "{_TABLE}"')
        conn.execute(
            f'ALTER TABLE "{tmp_table}" RENAME TO "{_TABLE}"'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_algorithm_id '
            f'ON "{_TABLE}"(algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS '
            f'idx_{_TABLE}_anchor_algorithm_id '
            f'ON "{_TABLE}"(anchor_algorithm_id)'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{_TABLE}_tag '
            f'ON "{_TABLE}"(tag)'
        )

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
            "anchor_algorithm_id": row.anchor_algorithm_id,
            "tag": row.tag,
            "framework_version": row.framework_version,
            "engine_type": row.engine_type,
            # ``None`` (the in-memory pooled-row sentinel) maps to the
            # SQL-level empty string so the composite PK
            # ``(bundle_path, engine_type, universe_key)`` collapses
            # NULLs deterministically (SQLite treats NULLs in a
            # composite PK as distinct, which would defeat upsert).
            "universe_key": row.universe_key or "",
            # ``None`` maps to the canonical ``'default'`` sentinel
            # so legacy single-study bundles share the v9.0 row
            # shape and Phase 3d — the composite PK includes
            # ``study_name`` and SQLite treats NULLs in PKs as
            # distinct, which would defeat upsert.
            "study_name": row.study_name or "default",
            "study_description": row.study_description,
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
            "anchor_algorithm_id": d.get("anchor_algorithm_id"),
            "tag": d.get("tag"),
            "bundle_path": d.get("bundle_path"),
            "framework_version": d.get("framework_version"),
            "engine_type": d.get("engine_type"),
            # SQL stores '' for the pooled cross-universe row; the
            # in-memory contract uses ``None`` for that sentinel.
            "universe_key": (d.get("universe_key") or None),
            "study_name": d.get("study_name"),
            "study_description": d.get("study_description"),
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
