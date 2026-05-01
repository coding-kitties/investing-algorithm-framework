"""
Content-aware checkpoint manifest hashing.

The checkpoint system identifies a completed backtest by its
``algorithm_id`` plus the backtest date range. That key cannot
distinguish between "the same experiment ran" and "the strategy
code or its parameters changed since the last run".

This module computes a ``manifest_hash`` for a strategy + date range
combination. Storing the hash next to each ``algorithm_id`` in
``checkpoints.json`` lets the backtest engine automatically rerun a
strategy whose code or parameters changed, without any user prompt.

The hash fingerprints:

- the strategy's instance attributes (parameters)
- the source code of the strategy's class
- the data sources (symbols, timeframe, type, market)
- the backtest date range

Optionally (off by default), the framework version can be mixed in.
This is opt-in because a framework upgrade does not always invalidate
prior backtest results.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Attributes ignored when fingerprinting a strategy instance. These are
# either internal state, transient runtime objects, or the algorithm_id
# itself (which is the lookup key, not the content being hashed).
_IGNORED_STRATEGY_ATTRS = frozenset(
    {
        "algorithm_id",
        "strategy_id",
        "decorated",
        "context",
        "traces",
        "_orders",
        "_trades",
    }
)


def _safe_repr(value: Any) -> str:
    """
    Return a stable, JSON-friendly representation of ``value``.

    Falls back to ``repr`` for objects that are not natively JSON
    serialisable. ``repr`` is used because it is deterministic for
    primitive types and exposes class identity for objects that don't
    implement ``__eq__`` / ``__hash__``.
    """
    try:
        return json.dumps(value, sort_keys=True, default=repr)
    except Exception:
        return repr(value)


def _strategy_params_fingerprint(strategy: Any) -> Dict[str, str]:
    """
    Build a sorted dict of (attr_name -> stable repr) for a strategy.

    Public, non-callable attributes set on the instance are included.
    Class-level type annotations and ``_IGNORED_STRATEGY_ATTRS`` are
    skipped.
    """
    fingerprint: Dict[str, str] = {}

    raw_dict = getattr(strategy, "__dict__", {}) or {}
    for name, value in raw_dict.items():
        if name.startswith("__"):
            continue
        if name in _IGNORED_STRATEGY_ATTRS:
            continue
        if callable(value):
            continue
        fingerprint[name] = _safe_repr(value)

    return dict(sorted(fingerprint.items()))


def _strategy_source_fingerprint(strategy: Any) -> str:
    """
    Return a hash of the strategy's class source code.

    Uses ``inspect.getsource`` on the class. If the source is not
    available (e.g. classes defined in the REPL or notebooks where
    the source can't be located), returns the qualified class name as
    a fallback so the hash stays stable but no longer reacts to code
    edits. A debug log is emitted in that case.
    """
    cls = strategy.__class__
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        logger.debug(
            "Could not read source for %s; falling back to class name "
            "for manifest hash",
            cls,
        )
        return f"<no-source>:{cls.__module__}.{cls.__qualname__}"

    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _data_sources_fingerprint(strategy: Any) -> List[str]:
    """
    Return a stable, sorted list of data-source identifiers used by
    the strategy.
    """
    data_sources = getattr(strategy, "data_sources", None) or []
    rendered = []
    for ds in data_sources:
        # DataSource objects are fully described by their identifier; we
        # also include the repr in case identifier is not implemented.
        ident = getattr(ds, "identifier", None)
        if callable(ident):
            try:
                ident = ident()
            except Exception:
                ident = None
        rendered.append(str(ident) if ident is not None else repr(ds))
    return sorted(rendered)


def _date_range_fingerprint(backtest_date_range: Any) -> str:
    """Return a stable string for a BacktestDateRange."""
    start = backtest_date_range.start_date.isoformat()
    end = backtest_date_range.end_date.isoformat()
    return f"{start}_{end}"


def compute_strategy_manifest_hash(
    strategy: Any,
    backtest_date_range: Any,
    framework_version: Optional[str] = None,
) -> str:
    """
    Compute a deterministic content-aware manifest hash for a single
    (strategy, date_range) pair.

    Args:
        strategy: A ``TradingStrategy`` instance (or anything exposing
            ``__dict__`` and ``data_sources``).
        backtest_date_range: A ``BacktestDateRange`` exposing
            ``start_date`` and ``end_date``.
        framework_version: Optional framework version to mix into the
            hash. When ``None`` (default) the framework version is
            excluded so framework upgrades do not invalidate
            checkpoints.

    Returns:
        A short (16-char) hex digest. Short because checkpoints.json is
        human-inspectable; collisions across the relevant scope (a
        single batch of backtests for one date range) are negligible.
    """
    payload: Dict[str, Any] = {
        "params": _strategy_params_fingerprint(strategy),
        "source": _strategy_source_fingerprint(strategy),
        "data_sources": _data_sources_fingerprint(strategy),
        "date_range": _date_range_fingerprint(backtest_date_range),
    }
    if framework_version is not None:
        payload["framework_version"] = framework_version

    serialized = json.dumps(payload, sort_keys=True, default=repr)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest[:16]


def get_checkpoint_hash_for_id(
    checkpoint_entry: Any,
    algorithm_id: str,
) -> Optional[str]:
    """
    Look up the stored manifest hash for ``algorithm_id`` in a single
    checkpoint entry (the value stored under one date-range key).

    The on-disk format for a checkpoint entry can be either:

    - a list of algorithm ids (legacy format), or
    - a dict mapping algorithm_id -> manifest_hash, or
    - a dict mapping algorithm_id -> {"manifest_hash": "..."}

    Returns:
        - The stored hash string if present.
        - ``None`` if the algorithm_id is checkpointed but no hash is
          recorded (legacy entry).
        - ``None`` if the algorithm_id is not in the entry. Callers
          should also use ``algorithm_id_in_entry`` to disambiguate.
    """
    if isinstance(checkpoint_entry, dict):
        value = checkpoint_entry.get(algorithm_id)
        if isinstance(value, dict):
            return value.get("manifest_hash")
        if isinstance(value, str):
            return value
        return None
    return None


def algorithm_id_in_entry(
    checkpoint_entry: Any,
    algorithm_id: str,
) -> bool:
    """Whether ``algorithm_id`` is checkpointed in this entry."""
    if isinstance(checkpoint_entry, dict):
        return algorithm_id in checkpoint_entry
    if isinstance(checkpoint_entry, list):
        return algorithm_id in checkpoint_entry
    return False


def normalize_checkpoint_entry(
    checkpoint_entry: Any,
) -> Dict[str, Optional[str]]:
    """
    Convert a checkpoint entry to the canonical
    ``{algorithm_id: manifest_hash | None}`` form.
    """
    if isinstance(checkpoint_entry, dict):
        result: Dict[str, Optional[str]] = {}
        for algo_id, value in checkpoint_entry.items():
            if isinstance(value, dict):
                result[algo_id] = value.get("manifest_hash")
            elif isinstance(value, str):
                result[algo_id] = value
            else:
                result[algo_id] = None
        return result
    if isinstance(checkpoint_entry, list):
        return {algo_id: None for algo_id in checkpoint_entry}
    return {}
