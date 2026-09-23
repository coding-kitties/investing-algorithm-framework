"""Run-local scalar projections shared by metric calculations.

Numeric values retain their original Python/NumPy types to preserve reduction
semantics. Nested domain graphs are decoded once, then released.
"""
from collections import namedtuple
from copy import copy
from functools import wraps


class SnapshotInput(namedtuple(
    'SnapshotInput', 'created_at total_value cash_flow',
)):
    __slots__ = ()

    def get_created_at(self):
        return self.created_at

    def get_total_value(self):
        return self.total_value


TradeInput = namedtuple('TradeInput', (
    'source_index opened_at closed_at status is_short amount open_price cost '
    'net_gain net_gain_absolute duration high_water_mark low_water_mark'
))


class SnapshotInputs(list):
    """Scalar rows with run-local shared resampling results."""

    def __init__(self, snapshots):
        super().__init__(SnapshotInput(
            snapshot.created_at, snapshot.total_value,
            getattr(snapshot, 'cash_flow', 0),
        ) for snapshot in snapshots)
        self.metric_cache = {}


def shared_snapshot_calculation(function):
    """Reuse resampling only for the private, run-local scalar projection."""
    @wraps(function)
    def calculate(snapshots, *args, **kwargs):
        if not isinstance(snapshots, SnapshotInputs):
            return function(snapshots, *args, **kwargs)
        key = (function, args, tuple(sorted(kwargs.items())))
        if key not in snapshots.metric_cache:
            snapshots.metric_cache[key] = function(snapshots, *args, **kwargs)
        return snapshots.metric_cache[key]
    return calculate


def prepare_metric_inputs(run):
    """Decode each history once without retaining nested orders/positions."""
    working = copy(run)
    trades = [TradeInput(
        index, trade.opened_at, trade.closed_at, trade.status, trade.is_short,
        trade.amount, trade.open_price, trade.cost, trade.net_gain,
        trade.net_gain_absolute, trade.duration,
        trade.high_water_mark, trade.low_water_mark,
    ) for index, trade in enumerate(run.trades)]
    object.__setattr__(working, 'trades', trades)
    object.__setattr__(working, 'portfolio_snapshots',
                       SnapshotInputs(run.portfolio_snapshots))
    return working