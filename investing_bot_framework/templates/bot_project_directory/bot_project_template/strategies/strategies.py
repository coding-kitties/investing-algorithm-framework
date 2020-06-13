from investing_bot_framework.core.strategies import Strategy
from investing_bot_framework.core.utils import TimeUnit

"""
Define here all your strategies
"""


class MyStrategy(Strategy):
    time_unit = TimeUnit.SECOND
    time_interval = 10
    id = 'my_strategy'

    def apply_strategy(self) -> None:
        pass
