from tests.resources import TestBase
from time import sleep


class TestDataProvider(TestBase):

    def setUp(self) -> None:
        super(TestDataProvider, self).setUp()
        self.scheduled_data_provider.register_strategy(self.strategy)
        self.algorithm_context.add_data_provider(self.scheduled_data_provider)

    def test(self) -> None:
        self.algorithm_context.start(1)
        self.assertEqual(1, self.scheduled_data_provider.cycles)
        self.algorithm_context.start(1)
        self.assertEqual(1, self.scheduled_data_provider.cycles)
        sleep(3)
        self.algorithm_context.start(1)
        self.assertEqual(2, self.scheduled_data_provider.cycles)
