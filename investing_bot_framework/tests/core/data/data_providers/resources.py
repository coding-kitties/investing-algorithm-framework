from typing import Dict, Any

from investing_bot_framework.core.events import Observer
from investing_bot_framework.core.data_providers import DataProvider


class TestDataProviderOne(DataProvider):

    id = 'TestDataProviderOne'

    def provide_data(self, **kwargs: Dict[str, Any]) -> Any:
        return "data_providers"


class TestDataProviderTwo(DataProvider):

    id = 'TestDataProviderTwo'

    def provide_data(self, **kwargs: Dict[str, Any]) -> Any:
        return "data_providers"


class TestObserver(Observer):

    def __init__(self) -> None:
        self.update_count = 0

    def update(self, observable, **kwargs) -> None:
        self.update_count += 1
