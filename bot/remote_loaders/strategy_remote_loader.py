import os
from typing import Dict, Any, List

from bot import OperationalException
from bot.strategy.strategy import Strategy


class StrategyRemoteLoader:

    def __init__(self, config: Dict[str, Any]):

        self._strategies: List[Strategy] = None

        if not config.get('strategies'):
            raise OperationalException(
                "Could not resolve strategies, please provide the strategy "
                "paths in your config file. You could also use de default strategies, that can be found in the "
                "strategies directory. If you have difficulties creating your own strategies, please see the "
                "documentation"
            )

        strategies = config.get('strategies')

        for strategy in strategies:
            path = strategy.get('path')
            self._strategies.append(self.load_strategy(path))

    @staticmethod
    def load_strategy(path: str) -> Strategy:

        if not path:
            raise OperationalException("Provided strategies has it file path not set")

        current_path = os.path.dirname(os.path.abspath(__file__))



