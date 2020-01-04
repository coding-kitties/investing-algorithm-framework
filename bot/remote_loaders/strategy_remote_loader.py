import logging
from pathlib import Path

from bot.strategies import Strategy
from bot import OperationalException
from bot.constants import PLUGIN_STRATEGIES_DIR
from bot.remote_loaders.remote_loader import RemoteLoader

logger = logging.getLogger(__name__)


class StrategyRemoteLoader(RemoteLoader):

    def load_strategy(self, strategy_class_name: str) -> Strategy:

        logger.info("Loading remote strategies ...")

        if not strategy_class_name:
            raise OperationalException("Provided strategies has it search class name not set")

        strategies_dir = Path(PLUGIN_STRATEGIES_DIR)
        modules = self.locate_python_modules(strategies_dir)
        location = self.locate_class(modules, strategy_class_name)
        generator = self.create_class_generators(location, strategy_class_name, Strategy)
        strategy: Strategy = next(generator, None)()

        if strategy and isinstance(strategy, Strategy):
            return strategy

        raise OperationalException(
            f"Impossible to load Strategy '{strategy_class_name}'. This strategy does not exist "
            "or contains Python code errors."
        )

