"""Strategy phase pipeline (v9.0).

Replaces the monolithic
:py:meth:`investing_algorithm_framework.app.strategy.TradingStrategy.run_strategy`
with a configurable sequence of :class:`StrategyPhase` objects.

See ``docs/architecture/strategy.md`` (when written) for the design
rationale and ``tests/services/strategy_phases/`` for parity tests
against the legacy code path.

Public surface:

    from investing_algorithm_framework.services.strategy_phases import (
        StrategyPhase,
        PhaseState,
        SizedIntent,
        EmittedOrder,
        CollectSignalsPhase,
        ResolveConflictsPhase,
        SizePositionsPhase,
        ApplyRiskBudgetPhase,
        EmitOrdersPhase,
        AttachRiskRulesPhase,
        RecordCooldownPhase,
        DEFAULT_PHASES,
    )
"""
from .base import StrategyPhase
from .phase_state import EmittedOrder, PhaseState, SizedIntent
from .evaluate_pipelines import EvaluatePipelinesPhase
from .collect_signals import CollectSignalsPhase
from .resolve_conflicts import ResolveConflictsPhase
from .size_positions import SizePositionsPhase
from .apply_risk_budget import ApplyRiskBudgetPhase
from .emit_orders import EmitOrdersPhase
from .attach_risk_rules import AttachRiskRulesPhase
from .record_cooldown import RecordCooldownPhase
from .default import DEFAULT_PHASES, build_default_phases

__all__ = [
    "StrategyPhase",
    "PhaseState",
    "SizedIntent",
    "EmittedOrder",
    "EvaluatePipelinesPhase",
    "CollectSignalsPhase",
    "ResolveConflictsPhase",
    "SizePositionsPhase",
    "ApplyRiskBudgetPhase",
    "EmitOrdersPhase",
    "AttachRiskRulesPhase",
    "RecordCooldownPhase",
    "DEFAULT_PHASES",
    "build_default_phases",
]
