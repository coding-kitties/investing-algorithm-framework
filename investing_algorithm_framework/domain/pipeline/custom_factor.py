"""User-extensible factor base class."""
from __future__ import annotations

from .factor import Factor


class CustomFactor(Factor):
    """Base class for user-defined factors.

    Subclass this and override :meth:`compute_panel` to compute factor
    values from a long-form OHLCV ``pl.DataFrame``. Set ``inputs`` to
    the OHLCV columns you need (default: ``["close"]``) and set
    ``window`` to the lookback in bars.

    Example::

        class MaxDrawdown(CustomFactor):
            inputs = ["close"]
            window = 252

            def compute_panel(self, panel):
                return (
                    panel.with_columns(
                        pl.col("close")
                        .rolling_max(self.window)
                        .over("symbol")
                        .alias("__rmax__")
                    )
                    .with_columns(
                        ((pl.col("close") / pl.col("__rmax__")) - 1.0)
                        .alias("__dd__")
                    )["__dd__"]
                )
    """
