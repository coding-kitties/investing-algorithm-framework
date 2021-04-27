from tests.resources import TestBase


class TestDataProvider(TestBase):

    def setUp(self) -> None:
        super(TestDataProvider, self).setUp()
        self.data_provider.register_strategy(self.strategy)
        self.algorithm_context.add_data_provider(self.relational_data_provider)

    def test(self) -> None:
        self.algorithm_context.start(1)
        self.assertEqual(0, self.relational_data_provider.cycles)
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.start(2)
        self.assertEqual(2, self.data_provider.cycles)
        self.assertEqual(1, self.relational_data_provider.cycles)
