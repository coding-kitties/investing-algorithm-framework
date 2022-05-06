from investing_algorithm_framework.app.stateless.action_handlers \
    .action_handler_strategy import ActionHandlerStrategy
from investing_algorithm_framework.configuration.constants import PORTFOLIOS, \
    STRATEGIES
from investing_algorithm_framework.core.models import Portfolio
from investing_algorithm_framework.core.portfolio_managers import \
    StatelessPortfolioManager


class RunStrategyHandler(ActionHandlerStrategy):

    def handle_event(self, payload, algorithm_context):

        for portfolio_key in payload[PORTFOLIOS]:
            portfolio_data = payload[PORTFOLIOS][portfolio_key]
            portfolio_data["identifier"] = portfolio_key

            algorithm_context.add_portfolio_manager(
                StatelessPortfolioManager.of_portfolio(
                    Portfolio.from_dict(portfolio_data)
                )
            )

        if STRATEGIES in payload:

            for strategy_identifier in payload[STRATEGIES]:
                algorithm_context.run_strategy(strategy_identifier)
        else:
            for strategy_identifier in algorithm_context.get_strategies():
                algorithm_context.run_strategy(strategy_identifier)
