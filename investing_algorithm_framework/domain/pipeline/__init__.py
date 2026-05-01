"""Pipeline API primitives.

Phase 1 (event-driven backtest only) of the Pipeline API tracked in
issue #438 / #501.

See ``docs/design/pipeline-api.md`` for the design rationale.
"""
from .factor import Factor
from .custom_factor import CustomFactor
from .filter import Filter
from .pipeline import Pipeline
from .factors import (
    Returns,
    AverageDollarVolume,
    SMA,
    RSI,
    Volatility,
)

__all__ = [
    "Pipeline",
    "Factor",
    "CustomFactor",
    "Filter",
    "Returns",
    "AverageDollarVolume",
    "SMA",
    "RSI",
    "Volatility",
]
