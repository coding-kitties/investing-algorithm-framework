"""Dispatches ``TradingStrategy.on_trade_*`` lifecycle callbacks.

Wired as a single process-wide singleton (see ``dependency_container.py``)
and shared by ``TradeService``/``TradeOrderEvaluator`` so trade-lifecycle
events (created, opened, closed, updated, stop-loss/take-profit
created/triggered) reach the strategy that placed the originating order —
in live trading and event-driven backtesting only; the vector engine has
no per-trade callback point and does not use this.

Performance: ``configure()`` runs once per run and caches, per strategy,
which of the 13 hook methods are actually overridden (identity-compared
against the ``TradingStrategy`` no-op defaults). ``dispatch()`` then
short-circuits on a single boolean when nothing is overridden, which is
the common case today, so strategies that don't use these hooks pay
effectively zero overhead in the per-bar/per-fill hot paths. The three
``on_trade_*_updated`` hooks fire only when a trailing stop-loss/
take-profit level actually moves, not on every bar, keeping the
per-bar cost to a single float comparison per active trailing rule.
"""
from logging import getLogger
from typing import Dict, FrozenSet, Optional

logger = getLogger(__name__)

TRADE_HOOK_NAMES = (
    "on_trade_created",
    "on_trade_opened",
    "on_trade_closed",
    "on_trade_updated",
    "on_trade_stop_loss_triggered",
    "on_trade_trailing_stop_loss_triggered",
    "on_trade_take_profit_triggered",
    "on_trade_stop_loss_created",
    "on_trade_trailing_stop_loss_created",
    "on_trade_take_profit_created",
    "on_trade_stop_loss_updated",
    "on_trade_trailing_stop_loss_updated",
    "on_trade_take_profit_updated",
)


class TradeHookDispatcher:
    """Routes trade-lifecycle events to the owning strategy instance."""

    def __init__(self):
        self._strategies_by_id: Dict[str, object] = {}
        self._active_hooks_by_id: Dict[str, FrozenSet[str]] = {}
        self._any_active = False
        self.context = None

    def configure(self, strategies, context) -> None:
        """
        (Re)compute the override cache for the given strategies. Called
        once per run (``EventLoopService.initialize``), not per tick.
        """
        from investing_algorithm_framework.app.strategy import (
            TradingStrategy,
        )

        self.context = context
        self._strategies_by_id = {}
        self._active_hooks_by_id = {}
        self._any_active = False

        for strategy in strategies or []:
            strategy_id = strategy.strategy_identifier
            self._strategies_by_id[strategy_id] = strategy
            overridden = frozenset(
                name for name in TRADE_HOOK_NAMES
                if getattr(type(strategy), name)
                is not getattr(TradingStrategy, name)
            )
            self._active_hooks_by_id[strategy_id] = overridden

            if overridden:
                self._any_active = True

    def dispatch(self, hook_name: str, trade: Optional[object]) -> None:
        """
        Call ``hook_name`` on the strategy that owns ``trade``
        (``trade.metadata["strategy_id"]``), if that strategy overrides
        it. No-op if no strategy overrides any trade hook, if ``trade``
        is ``None``, or if the owning strategy can't be resolved.
        """
        if not self._any_active or trade is None:
            return

        strategy_id = (getattr(trade, "metadata", None) or {}).get(
            "strategy_id"
        )

        if strategy_id is not None:
            candidate_ids = (strategy_id,)
        else:
            # Unattributed trade (e.g. created outside the normal
            # strategy pipeline, such as directly via tests) —
            # broadcast to every strategy overriding this hook.
            candidate_ids = tuple(self._strategies_by_id)

        for candidate_id in candidate_ids:
            if hook_name not in self._active_hooks_by_id.get(
                candidate_id, ()
            ):
                continue

            strategy = self._strategies_by_id[candidate_id]

            try:
                getattr(strategy, hook_name)(self.context, trade)
            except Exception:
                logger.exception(
                    "Strategy hook %s raised for trade %s",
                    hook_name, getattr(trade, "id", None),
                )
