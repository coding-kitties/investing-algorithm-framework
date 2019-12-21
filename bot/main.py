import logging
from typing import Any, List

# Call settings for general configuration
# from bot import setup
# from bot.configuration import Arguments
# from bot.configuration import Configuration
# from bot.bot import Bot
# from bot.services import ServiceManager


from abc import ABC, abstractmethod
from typing import Dict, Any
from pandas import DataFrame
import numpy as np
import sys
import time
from datetime import timedelta
from bot import utils
from threading import active_count
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class DataProvider(ABC):

    def __init__(self):
        self._data: DataFrame = None

    def get_name(self) -> str:
        return self.__class__.__name__

    @property
    def data(self):
        return self._data

    def start(self):
        self._data = self.scrape_data()

    @abstractmethod
    def scrape_data(self) -> DataFrame:
        pass


class FMPDataProvider(DataProvider):

    def scrape_data(self, ticker: str = None) -> DataFrame:
        print("faigfheaoigho")
        time.sleep(5)
        print("faigfheaoigho")
        return DataFrame(np.random.randint(1000, size=10000), columns=['ip'])


class DataProviderManager:

    def __init__(self):
        self.registered_data_providers = [FMPDataProvider()]
        self._jobs = []

    def start_data_providers(self) -> None:

        for data_providers in self.registered_data_providers:
            job = utils.ScheduledThread(interval=timedelta(seconds=10), execute=data_providers.start)
            job.start()
            self._jobs.append(job)

    def stop_data_providers(self) -> None:

        for job in self._jobs:
            job.stop()


def main(sysargv: List[str] = None) -> None:
    """
    This function will initiate the bot and start the trading loop.
    :return: None
    """

    try:
        manager = DataProviderManager()
        manager.start_data_providers()
        print(active_count())
        print('halo')
        i = 0

        while 1:
            print('hallo')
            time.sleep(3)

    except SystemExit as e:
        return_code = e
    except KeyboardInterrupt:
        logger.info('SIGINT received, aborting ...')
        return_code = 0
    except Exception:
        logger.exception('Fatal exception!')
    finally:
        sys.exit()


if __name__ == "__main__":
    main()
