import logging
from typing import Dict, Any
from abc import abstractmethod

from investing_algorithm_framework.core.workers import ScheduledWorker

logger = logging.getLogger(__name__)


class Strategy(ScheduledWorker):
    """
    Class Strategy
    """

    @abstractmethod
    def apply_strategy(self) -> None:
        pass

    def work(self, **kwargs: Dict[str, Any]) -> None:
        logger.info("Starting strategy {}".format(self.get_id()))
        self.apply_strategy()
