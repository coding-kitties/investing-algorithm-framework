from tests.resources.test_base import TestBase


class TestAlgorithmContextInitialization(TestBase):

    def setUp(self) -> None:
        super(TestAlgorithmContextInitialization, self).setUp()
        self.algorithm_context.add_initializer(self.context_initializer)
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

    def test_running_single_cycle(self) -> None:
        self.algorithm_context.start(cycles=2)
        self.assertEqual(2, self.data_provider.cycles)
        self.assertEqual(1, self.context_initializer.called)
