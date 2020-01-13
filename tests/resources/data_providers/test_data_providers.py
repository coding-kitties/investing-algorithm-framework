from typing import Dict, Any

from pandas import DataFrame

from tests.utils import random_numpy_data_frame
from bot.data import DataProvider


class SampleDataProviderOne(DataProvider):

    def provide_data(self, **kwargs: Dict[str, Any]) -> DataFrame:
        return random_numpy_data_frame()

    def get_id(self) -> str:
        return self.__class__.__name__


class SampleDataProviderTwo(DataProvider):

    def provide_data(self, **kwargs: Dict[str, Any]) -> DataFrame:
        return random_numpy_data_frame()

    def get_id(self) -> str:
        return self.__class__.__name__
