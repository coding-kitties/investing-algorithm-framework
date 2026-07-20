"""Abstract base class for v9.0 strategy phases.

A phase encapsulates one step of the
:py:meth:`TradingStrategy.run_strategy` pipeline. Subclasses
implement :meth:`run` and mutate the shared :class:`PhaseState`
in well-defined slots (see :class:`PhaseState` for the contract).

Phases are intended to be **stateless** between iterations — any
mutable state belongs on :class:`PhaseState` (per-iteration) or on
the :class:`TradingStrategy` instance (cross-iteration, e.g.
cooldown counters). This keeps phases freely shareable across
strategies and trivially unit-testable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .phase_state import PhaseState


class StrategyPhase(ABC):
    """One step of the v9.0 strategy pipeline.

    Subclasses must override :meth:`run`. The ``name`` class
    attribute is used by traces and error messages; subclasses may
    override it to provide a more specific label, but the default
    derives from the class name.
    """

    #: Optional human-readable name for trace / error output.
    #: Defaults to the subclass name when ``None``.
    name: str | None = None

    @abstractmethod
    def run(self, state: PhaseState) -> None:  # pragma: no cover - abstract
        """Mutate ``state`` according to this phase's contract.

        Implementations should *not* return a value — all
        communication flows through :class:`PhaseState`.
        """
        raise NotImplementedError

    # ---- introspection / debugging ---------------------------------- #
    @property
    def display_name(self) -> str:
        return self.name or type(self).__name__

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<{self.display_name}>"
