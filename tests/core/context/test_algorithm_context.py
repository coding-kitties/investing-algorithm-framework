from unittest import TestCase

from investing_algorithm_framework.core.context import AlgorithmContext, \
    AlgorithmContextInitializer
from investing_algorithm_framework import DataProvider, AbstractOrderExecutor, \
    AbstractPortfolioManager, Strategy
from tests.resources.utils import random_string


class MyStrategy(Strategy):
    cycles = 0

    def on_raw_data(self, data_provider_id, data, algorithm_context):
        MyStrategy.cycles += 1
        algorithm_context.perform_limit_order('test_broker', 'btc', 10, 10, 10)


class MyDataProvider(DataProvider):
    cycles = 0
    registered_strategies = [MyStrategy()]

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.cycles += 1
        return 'data'


class MyOrderExecutor(AbstractOrderExecutor):
    cycles = 0
    execute_limit_order_called = False

    def __init__(self):
        super(MyOrderExecutor, self).__init__("test_broker")

    def execute_limit_order(
            self,
            asset: str,
            max_price: float,
            quantity: int,
            algorithm_context: AlgorithmContext, **kwargs
    ):
        MyOrderExecutor.cycles += 1
        MyOrderExecutor.execute_limit_order_called = True


class MyPortfolioManager(AbstractPortfolioManager):
    portfolio_size_called = False
    free_portfolio_size_called = False
    get_allocated_portfolio_size_called = False
    get_allocated_asset_size_called = False

    def __init__(self):
        super(MyPortfolioManager, self).__init__("test_broker")

    def get_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.portfolio_size_called = True
        return 200

    def get_free_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.free_portfolio_size_called = True
        return 200

    def get_allocated_portfolio_size(self, algorithm_context: AlgorithmContext):
        MyPortfolioManager.get_allocated_portfolio_size_called = True
        return 0

    def get_allocated_asset_size(
            self, asset, algorithm_context: AlgorithmContext
    ):
        MyPortfolioManager.get_allocated_asset_size_called = True
        return 0


class MyInitializer(AlgorithmContextInitializer):
    initializer_called = False

    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        MyInitializer.initializer_called = True


class TestAlgorithmContext(TestCase):

    def setUp(self) -> None:
        MyOrderExecutor.cycles = 0
        MyPortfolioManager.portfolio_size_called = False
        MyPortfolioManager.free_portfolio_size_called = False
        MyPortfolioManager.get_allocated_portfolio_size_called = False
        MyPortfolioManager.get_allocated_asset_size_called = False
        MyDataProvider.cycles = 0
        MyStrategy.cycles = 0

    def test_data_component_registrations(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()]
        )
        self.assertIsNotNone(context)
        self.assertIsNotNone(context.data_providers)
        self.assertEqual(1, len(context.data_providers))
        self.assertEqual(1, len(context.order_executors))
        self.assertEqual(1, len(context.portfolio_managers))

        with self.assertRaises(Exception) as exc_info:
            AlgorithmContext(
                data_providers=[MyDataProvider],
                order_executors=[MyOrderExecutor],
                portfolio_managers=[MyPortfolioManager]
            )

        self.assertEqual(
            str(exc_info.exception),
            "Data provider must be an instance "
            "of the AbstractDataProvider class"
        )

    def test_context_id_creation(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()]
        )
        self.assertIsNotNone(context.algorithm_id)

        context = AlgorithmContext(
            algorithm_id='test_context',
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()]
        )
        self.assertIsNotNone(context.algorithm_id)
        self.assertEqual(context.algorithm_id, 'test_context')

    def test_running_single_cycle(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()],
            cycles=1,
            initializer=MyInitializer()
        )

        context.start()
        self.assertEqual(1, MyDataProvider.cycles)
        self.assertEqual(1, MyStrategy.cycles)
        self.assertFalse(MyPortfolioManager.portfolio_size_called)
        self.assertTrue(MyPortfolioManager.free_portfolio_size_called)
        self.assertTrue(MyOrderExecutor.execute_limit_order_called)
        self.assertTrue(MyInitializer.initializer_called)

    def test_running_two_cycles(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()],
            cycles=2,
            initializer=MyInitializer()
        )

        context.start()
        self.assertEqual(2, MyDataProvider.cycles)
        self.assertEqual(2, MyStrategy.cycles)
        self.assertFalse(MyPortfolioManager.portfolio_size_called)
        self.assertTrue(MyPortfolioManager.free_portfolio_size_called)
        self.assertTrue(MyOrderExecutor.execute_limit_order_called)
        self.assertTrue(MyInitializer.initializer_called)
