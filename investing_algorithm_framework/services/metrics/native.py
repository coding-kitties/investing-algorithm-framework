"""Optional native raw and cash-flow-adjusted risk metrics."""
from datetime import datetime
import math

import numpy as np


class NativeMetricsUnsupported(ValueError):
    """Inputs cannot preserve Python metric semantics in the native kernel."""


NATIVE_METRICS = frozenset({
    'equity_curve', 'drawdown_series', 'max_drawdown',
    'max_drawdown_absolute', 'max_drawdown_duration', 'twr_equity_curve',
    'twr_drawdown_series', 'twr_max_drawdown', 'twr_max_drawdown_duration',
})


def native_risk_metrics(snapshots):
    import iaf_confluence_native as native

    if getattr(native, 'DRAWDOWN_SEMANTICS_VERSION', None) != 'drawdown-v1':
        raise NativeMetricsUnsupported('Native risk metric version mismatch')
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.created_at)
    values, flows, times, elapsed = [], [], [], []
    for snapshot in ordered:
        value = snapshot.total_value
        flow = getattr(snapshot, 'cash_flow', 0) or 0
        if any(
            type(number) not in (int, float, np.float64)
            or (type(number) is int and abs(number) > 2 ** 52)
            or not math.isfinite(number)
            for number in (value, flow)
        ):
            raise NativeMetricsUnsupported('Unsupported equity numeric type')
        timestamp = snapshot.created_at
        if type(timestamp) is not datetime:
            raise NativeMetricsUnsupported('Native metrics require datetimes')
        if times and timestamp.tzinfo is not times[0].tzinfo:
            raise NativeMetricsUnsupported('Mixed timestamp timezones')
        times.append(timestamp)
        delta = timestamp - times[0]
        offset = (delta.days * 86400 + delta.seconds) * 1000000
        offset += delta.microseconds
        if not 0 <= offset <= 2 ** 63 - 1:
            raise NativeMetricsUnsupported('Timestamp range exceeds int64')
        values.append(value)
        flows.append(float(flow))
        elapsed.append(offset)
    try:
        raw, growth, adjusted = native.risk_metrics(values, flows, elapsed)
    except ValueError as exc:
        raise NativeMetricsUnsupported(str(exc)) from exc
    absolute = abs(values[raw[4]] - values[raw[5]]) if raw[2] else 0.0
    return {
        'equity_curve': list(zip(values, times)),
        'drawdown_series': list(zip(raw[0], times)),
        'max_drawdown': raw[1],
        'max_drawdown_absolute': absolute,
        'max_drawdown_duration': raw[3],
        'twr_equity_curve': list(zip(growth, times)),
        'twr_drawdown_series': list(zip(adjusted[0], times)),
        'twr_max_drawdown': adjusted[1],
        'twr_max_drawdown_duration': adjusted[3],
    }
