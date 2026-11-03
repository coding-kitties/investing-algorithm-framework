"""Opt-in native indicator evaluation before signal collection."""
from .base import StrategyPhase


class EvaluateIndicatorsPhase(StrategyPhase):
    name = "evaluate_indicators"

    def run(self, state):
        strategy = state.strategy
        if not getattr(strategy, "indicator_configs", ()):
            return
        engine = getattr(strategy, "_indicator_engine", None)
        if engine is None:
            engine = strategy.create_indicator_engine()
            strategy._indicator_engine = engine
        confluence_options = getattr(strategy, "get_confluence_evaluation_options", None)
        inactive = getattr(strategy, "get_inactive_confluence_cards", None)
        if confluence_options:
            options = confluence_options(state.context)
            state.data["_confluence_evaluation_options"] = options
        else:
            options = {"inactive_cards": inactive(state.context)} if inactive else {}
        if "inactive_cards" in options:
            state.data["_inactive_confluence_cards"] = options["inactive_cards"]
        state.data["indicators"] = engine.evaluate(
            state.data, as_of=state.current_datetime,
            **options,
        )
        state.trace("evaluate_indicators.count", len(strategy.indicator_configs))
