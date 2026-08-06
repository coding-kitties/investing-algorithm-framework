"""ExecutionConfig — captures the cost/fill assumptions of a Study.

Studies are the algorithm-centric unit of evidence in a backtest
bundle (see ``docs/design/multi-study-bundle.md``). Two studies of
the same algorithm can be run under different cost assumptions —
e.g. an optimistic sweep vs. a pessimistic sweep, or a live-fee
overlay vs. a mid-point overlay. :class:`ExecutionConfig` snapshots
those assumptions so a reader can audit or reproduce the runs that
produced a study's metrics.

The config is stored as plain ``dict`` snapshots (produced by the
respective model's ``to_dict()`` method) rather than pickled
instances. This keeps the bundle format cross-version-safe and
human-inspectable at the cost of requiring the target class to be
importable at load time — user-defined subclasses that aren't
imported when the bundle is opened will round-trip as ``None`` with
a warning (see :meth:`SlippageModel.from_dict`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionConfig:
    """Snapshot of the execution assumptions under which a study's
    runs were produced.

    Attributes:
        blotter_type: Class name of the :class:`Blotter` used
            (``"SimulationBlotter"``, ``"DefaultBlotter"``, or a
            user subclass name). Identity-only — parameters live on
            the model fields below.
        slippage_model: ``{"type": ..., "params": {...}}`` snapshot
            of the blotter's :class:`SlippageModel`, or ``None`` when
            no model was configured.
        commission_model: Same shape as ``slippage_model`` for the
            blotter's :class:`CommissionModel`.
        fill_model: Same shape for the blotter's :class:`FillModel`.
        metadata: Free-form extra metadata (e.g. blotter subclass
            module path for user-defined blotters, runtime flags like
            ``dynamic_position_sizing`` or ``fill_missing_data``).
    """

    blotter_type: Optional[str] = None
    slippage_model: Optional[Dict[str, Any]] = None
    commission_model: Optional[Dict[str, Any]] = None
    fill_model: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_runtime(
        cls,
        *,
        blotter=None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionConfig":
        """Build an :class:`ExecutionConfig` from live runtime objects.

        Args:
            blotter: The :class:`Blotter` instance in use, typically
                a :class:`SimulationBlotter`. Its ``slippage_model``,
                ``commission_model``, and ``fill_model`` are captured
                via each model's ``to_dict()``. ``None`` leaves the
                model fields unset.
            metadata: Optional extra dict merged into
                :attr:`metadata`.

        Returns:
            ExecutionConfig: A fully populated snapshot.
        """
        blotter_type: Optional[str] = None
        slip = com = fil = None

        if blotter is not None:
            blotter_type = type(blotter).__name__
            _slip = getattr(blotter, "slippage_model", None)
            _com = getattr(blotter, "commission_model", None)
            _fil = getattr(blotter, "fill_model", None)
            if _slip is not None and hasattr(_slip, "to_dict"):
                slip = _slip.to_dict()
            if _com is not None and hasattr(_com, "to_dict"):
                com = _com.to_dict()
            if _fil is not None and hasattr(_fil, "to_dict"):
                fil = _fil.to_dict()

        return cls(
            blotter_type=blotter_type,
            slippage_model=slip,
            commission_model=com,
            fill_model=fil,
            metadata=dict(metadata or {}),
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return ``True`` when no execution info has been captured."""
        return (
            self.blotter_type is None
            and self.slippage_model is None
            and self.commission_model is None
            and self.fill_model is None
            and not self.metadata
        )

    def rehydrate_slippage_model(self):
        """Return the reconstructed :class:`SlippageModel` instance
        (or ``None``). Requires the target class to be importable."""
        from investing_algorithm_framework.domain.blotter \
            import SlippageModel
        return SlippageModel.from_dict(self.slippage_model)

    def rehydrate_commission_model(self):
        """Return the reconstructed :class:`CommissionModel` instance
        (or ``None``). Requires the target class to be importable."""
        from investing_algorithm_framework.domain.blotter \
            import CommissionModel
        return CommissionModel.from_dict(self.commission_model)

    def rehydrate_fill_model(self):
        """Return the reconstructed :class:`FillModel` instance
        (or ``None``). Requires the target class to be importable."""
        from investing_algorithm_framework.domain.blotter import FillModel
        return FillModel.from_dict(self.fill_model)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly dict for bundle serialisation."""
        return {
            "blotter_type": self.blotter_type,
            "slippage_model": self.slippage_model,
            "commission_model": self.commission_model,
            "fill_model": self.fill_model,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(
        cls, data: Optional[Dict[str, Any]]
    ) -> Optional["ExecutionConfig"]:
        """Reconstruct an :class:`ExecutionConfig` from :meth:`to_dict`
        output. Returns ``None`` for ``None`` input."""
        if data is None:
            return None
        return cls(
            blotter_type=data.get("blotter_type"),
            slippage_model=data.get("slippage_model"),
            commission_model=data.get("commission_model"),
            fill_model=data.get("fill_model"),
            metadata=dict(data.get("metadata") or {}),
        )
