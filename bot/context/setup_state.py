import logging
from typing import List

from bot.context.bot_state import BotState
from bot.context.bot_context import BotContext
from bot.data import DataProvider, DataProviderExecutor
from bot.context.data_providing_state import DataProvidingState
from bot.strategies import ObservableStrategy, StrategyExecutor
from bot.configuration.resolvers import get_data_provider_configurations, get_strategy_plugins, \
    get_strategy_templates, get_strategy_configurations, get_data_provider_plugins, get_data_provider_templates

logger = logging.getLogger(__name__)


class SetupState(BotState):

    def __init__(self):
        super(SetupState, self).__init__()

        logger.info("Initializing setup state ...")

    def run(self):
        logger.info("Setup state started ...")

        context = BotContext()

        # Configure and start all the services

        # Initialize all data providers
        data_providers: List[DataProvider] = self._initialize_data_providers()
        context.data_provider_executor = DataProviderExecutor(data_providers)

        # Initializing all strategies
        strategies: List[ObservableStrategy] = self._initialize_strategies()
        context.strategy_executor = StrategyExecutor(strategies)

        logger.info("Transitioning to data providing state ...")

        context.transition_to(DataProvidingState)
        context.run()

    @classmethod
    def _initialize_data_providers(cls) -> List[DataProvider]:
        context = BotContext()

        data_providers: List[DataProvider] = []
        data_provider_configurations = get_data_provider_configurations(context.config)

        # Load plugins
        data_provider_plugins = get_data_provider_plugins(data_provider_configurations)

        # Load templates
        data_provider_templates = get_data_provider_templates(data_provider_configurations)

        if data_provider_plugins is not None:
            data_providers += data_provider_plugins

        if data_provider_templates is not None:
            data_providers += data_provider_templates

        return data_providers

    @classmethod
    def _initialize_strategies(cls) -> List[ObservableStrategy]:
        context = BotContext()

        strategies: List[ObservableStrategy] = []
        strategy_configurations = get_strategy_configurations(context.config)

        # Load plugins
        strategy_plugins = get_strategy_plugins(strategy_configurations)

        # Load templates
        strategy_templates = get_strategy_templates(strategy_configurations)

        if strategy_plugins is not None:
            strategies += [ObservableStrategy(strategy) for strategy in strategy_plugins]

        if strategy_templates is not None:
            strategies += [ObservableStrategy(strategy) for strategy in strategy_templates]

        return strategies

    def stop(self):
        # Stopping all services
        pass

    def reconfigure(self):
        # Clean up and reconfigure all the services
        pass
