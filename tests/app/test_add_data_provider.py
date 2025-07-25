from datetime import datetime

from investing_algorithm_framework import DataProvider, DataSource
from tests.resources import TestBase

class DataProviderTest(DataProvider):

    def has_data(self, data_source: DataSource, start_date: datetime = None,
                 end_date: datetime = None) -> bool:
        return True

    def get_data(self, data_source: DataSource, date: datetime = None,
                 start_date: datetime = None, end_date: datetime = None,
                 save: bool = False):
        return None

    def prepare_backtest_data(self, data_source: DataSource,
                              backtest_start_date, backtest_end_date) -> None:
        pass

    def get_backtest_data(self, data_source: DataSource,
                          backtest_index_date: datetime,
                          backtest_start_date: datetime = None,
                          backtest_end_date: datetime = None) -> None:
        return None


class Test(TestBase):

    def test_add(self):
        self.app.add_data_provider(DataProviderTest)
        self.app.initialize_data_sources()
        self.assertEqual(1, self.app.container.data_provider_service.count())
