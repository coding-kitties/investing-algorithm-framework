"""Fast ISO-8601 datetime parsing helper.

``dateutil.parser.parse`` is the bottleneck in :class:`Backtest` loading
(see issue #487 profiling notes). The strings emitted by :py:meth:`Backtest.to_dict`
are always produced by :py:meth:`datetime.isoformat`, so the standard-library
:py:meth:`datetime.fromisoformat` parser handles them ~50x faster.

This helper:

- Returns ``None`` for falsy / ``None`` values.
- Passes already-parsed :class:`datetime.datetime` objects through unchanged.
- Tries :py:meth:`datetime.fromisoformat` first (fast path).
- Falls back to ``dateutil.parser.parse`` for anything exotic.
"""
from datetime import datetime


def parse_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        pass
    from dateutil.parser import parse as _du_parse
    return _du_parse(value)
