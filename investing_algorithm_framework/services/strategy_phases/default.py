"""Default phase pipeline for v9.0 :class:`TradingStrategy`.

``DEFAULT_PHASES`` is the ordered tuple of phase classes that
:class:`TradingStrategy` instantiates when the user does not
provide a custom ``phases = [...]`` override. The ordering
reproduces the legacy ``run_strategy`` behaviour:

    Collect → Resolve → Size → Risk-budget → Emit → Attach → Record

:func:`build_default_phases` returns a fresh list of phase
*instances* so each strategy gets its own (currently stateless,
but the contract leaves room for future per-instance state).
"""
from __future__ import annotations

from typing import List, Tuple, Type

from .apply_risk_budget import ApplyRiskBudgetPhase
from .attach_risk_rules import AttachRiskRulesPhase
from .base import StrategyPhase
from .collect_signals import CollectSignalsPhase
from .emit_orders import EmitOrdersPhase
from .evaluate_pipelines import EvaluatePipelinesPhase
from .record_cooldown import RecordCooldownPhase
from .resolve_conflicts import ResolveConflictsPhase
from .size_positions import SizePositionsPhase


#: The canonical phase ordering, exported as a tuple of *classes*
#: for declarative use (e.g. ``phases = DEFAULT_PHASES``).
DEFAULT_PHASES: Tuple[Type[StrategyPhase], ...] = (
    EvaluatePipelinesPhase,
    CollectSignalsPhase,
    ResolveConflictsPhase,
    SizePositionsPhase,
    ApplyRiskBudgetPhase,
    EmitOrdersPhase,
    AttachRiskRulesPhase,
    RecordCooldownPhase,
)


def build_default_phases() -> List[StrategyPhase]:
    """Return a fresh list of phase instances using the default
    ordering. Called by :class:`TradingStrategy` when ``phases`` is
    left at the class default.
    """
    return [phase_cls() for phase_cls in DEFAULT_PHASES]
