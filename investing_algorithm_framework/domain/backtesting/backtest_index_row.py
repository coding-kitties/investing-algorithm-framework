"""Typed Tier-1 row contract for the tiered backtest store (epic #540).

A :class:`BacktestIndexRow` is the authoritative *flat, scalar-only*
view of a backtest. It is what gets stored as a single row in:

* the :class:`BacktestIndex` Parquet sidecar produced by
  :func:`save_backtests_to_directory`;
* the SQLite index built by ``iaf index`` (epic #540 phase 2);
* the Tier-1 SQL table in any tiered store implementation
  (``LocalTieredStore`` and the closed-source remote stores).

The schema is **deliberately frozen** — adding a new column is an
explicit decision and a doc update. Callers can always stash
non-canonical fields in :pyattr:`extras` (a JSON-friendly dict) which
is round-tripped opaquely.

This row is built without decoding any heavy time-series payloads;
it is safe to materialise from a bundle opened with
``Backtest.open(path, summary_only=True)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional

from .backtest_summary_metrics import BacktestSummaryMetrics


# Prefix used when flattening the nested summary metrics into a
# single-level dict (e.g. for Parquet / SQL columns). Kept as a
# module-level constant so consumers can reuse it without hard-coding
# the string in two places.
SUMMARY_FIELD_PREFIX = "summary."


@dataclass
class BacktestIndexRow:
    """One row of the backtest index — the Tier-1 contract.

    Field groups follow the design doc
    (``docs/design/tiered-backtest-storage.md`` §3.1):

    * **Identity** — ``algorithm_id``, ``tag``, ``bundle_path``
    * **Provenance** — ``framework_version``, ``engine_type``,
      ``risk_free_rate``
    * **Config** — ``parameters``, ``strategy_ids``, ``number_of_runs``
    * **Scalar metrics** — :pyattr:`summary_metrics`, the existing
      :class:`BacktestSummaryMetrics` dataclass
    * **Forward-compat** — :pyattr:`extras`, a free-form dict the
      bundle reader populates for non-canonical scalar fields

    Notes:
        The schema is intentionally flat for the wire shapes that need
        flatness (Parquet, SQL). For ergonomic Python use, prefer
        accessing :pyattr:`summary_metrics` directly.
    """

    # -- Identity --------------------------------------------------------
    algorithm_id: Optional[str] = None
    tag: Optional[str] = None
    bundle_path: Optional[str] = None

    # -- Provenance ------------------------------------------------------
    framework_version: Optional[str] = None
    engine_type: Optional[str] = None
    risk_free_rate: Optional[float] = None

    # -- Config ----------------------------------------------------------
    parameters: Dict[str, Any] = field(default_factory=dict)
    strategy_ids: List[Any] = field(default_factory=list)
    number_of_runs: int = 0

    # -- Scalar metrics --------------------------------------------------
    summary_metrics: Optional[BacktestSummaryMetrics] = None

    # -- Forward-compat --------------------------------------------------
    extras: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Flat-dict round-trip (Parquet / SQL / JSON wire shape)
    # ------------------------------------------------------------------
    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten into a single-level dict.

        Summary-metric scalars are emitted under
        :data:`SUMMARY_FIELD_PREFIX` keys (``summary.sharpe_ratio``
        etc.). Complex fields (``parameters``, ``strategy_ids``) are
        JSON-encoded so the result fits any tabular sink.
        """
        out: Dict[str, Any] = {
            "algorithm_id": self.algorithm_id,
            "tag": self.tag,
            "bundle_path": self.bundle_path,
            "framework_version": self.framework_version,
            "engine_type": self.engine_type,
            "risk_free_rate": self.risk_free_rate,
            "number_of_runs": self.number_of_runs,
        }

        # parameters / strategy_ids → JSON for tabular round-trip
        out["parameters"] = (
            _safe_json(self.parameters) if self.parameters else None
        )
        out["strategy_ids"] = (
            _safe_json(self.strategy_ids) if self.strategy_ids else None
        )

        # Scalar summary metrics, prefixed
        if self.summary_metrics is not None:
            for k, v in self.summary_metrics.to_dict().items():
                if isinstance(v, (int, float, str, bool)) or v is None:
                    out[f"{SUMMARY_FIELD_PREFIX}{k}"] = v

        # Forward-compat extras, prefixed to avoid colliding with the
        # canonical column set.
        for k, v in (self.extras or {}).items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                out[f"extras.{k}"] = v

        return out

    @classmethod
    def from_flat_dict(cls, row: Dict[str, Any]) -> "BacktestIndexRow":
        """Reconstruct a row from the flat dict shape produced by
        :meth:`to_flat_dict`. Unknown keys land in :pyattr:`extras`."""
        canonical = {f.name for f in fields(cls)} - {
            "summary_metrics", "extras"
        }

        kwargs: Dict[str, Any] = {}
        summary_dict: Dict[str, Any] = {}
        extras: Dict[str, Any] = {}

        for k, v in row.items():
            if k in canonical:
                if k in ("parameters", "strategy_ids"):
                    if v is None:
                        kwargs[k] = {} if k == "parameters" else []
                        continue
                    if isinstance(v, str):
                        try:
                            kwargs[k] = json.loads(v)
                            continue
                        except (TypeError, ValueError):
                            pass
                kwargs[k] = v
            elif k.startswith(SUMMARY_FIELD_PREFIX):
                summary_dict[k[len(SUMMARY_FIELD_PREFIX):]] = v
            elif k.startswith("extras."):
                extras[k[len("extras."):]] = v
            else:
                # Unknown key — preserve under extras (round-trip safety).
                extras[k] = v

        kwargs.setdefault("parameters", {})
        kwargs.setdefault("strategy_ids", [])

        return cls(
            **kwargs,
            summary_metrics=(
                BacktestSummaryMetrics.from_dict(summary_dict)
                if summary_dict else None
            ),
            extras=extras,
        )


def _safe_json(obj: Any) -> Optional[str]:
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return None
