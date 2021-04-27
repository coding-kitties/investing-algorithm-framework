from tests.resources import TestBase


class TestStrategy(TestBase):

    def setUp(self) -> None:
        super(TestStrategy, self).setUp()
        self.data_provider.registered_strategies.append(self.strategy)
        self.algorithm_context.add_data_provider(self.data_provider)

    def test_run(self):
        self.algorithm_context.start(cycles=1)
        self.assertEqual(1, len(self.algorithm_context.data_providers))
        self.assertEqual(1, self.strategy.called)
