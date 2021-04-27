from tests.resources import TestBase


class TestAlgorithmContext(TestBase):

    def setUp(self) -> None:
        super(TestAlgorithmContext, self).setUp()
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

    def test_data_provider_registration(self) -> None:
        self.assertIsNotNone(self.algorithm_context)
        self.assertIsNotNone(self.algorithm_context.data_providers)
        self.assertEqual(1, len(self.algorithm_context.data_providers))
        self.algorithm_context.add_data_provider(self.data_provider)
        self.assertEqual(2, len(self.algorithm_context.data_providers))

    def test_portfolio_manager_registration(self) -> None:
        self.assertIsNotNone(self.algorithm_context)
        self.assertIsNotNone(self.algorithm_context.portfolio_managers)
        self.assertEqual(1, len(self.algorithm_context.portfolio_managers))

    def test_order_executor_registration(self) -> None:
        self.assertIsNotNone(self.algorithm_context) 
        self.assertIsNotNone(self.algorithm_context.order_executors)
        self.assertEqual(1, len(self.algorithm_context.order_executors))

    def test_running_single_cycle(self) -> None:
        self.algorithm_context.start(cycles=1)
        self.assertEqual(1, self.data_provider.cycles)
        self.algorithm_context.start(cycles=2)
        self.assertEqual(3, self.data_provider.cycles)
