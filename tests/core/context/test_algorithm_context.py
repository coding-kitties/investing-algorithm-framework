from typing import Dict
from unittest import TestCase

from investing_algorithm_framework.core.context import AlgorithmContext, \
    AlgorithmContextInitializer, AlgorithmContextConfiguration
from investing_algorithm_framework import DataProvider, AbstractOrderExecutor, AbstractPortfolioManager, Strategy
from tests.resources.utils import random_string


class MyDataProvider(DataProvider):
    cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.cycles += 1
        return 'data'


class MyOrderExecutor(AbstractOrderExecutor):

    def __init__(self):
        super(MyOrderExecutor, self).__init__("test_broker")

    def execute_limit_order(
            self, asset: str, max_price: float, quantity: int, algorithm_context: AlgorithmContext, **kwargs
    ):
        pass


class MyPortfolioManager(AbstractPortfolioManager):

    def __init__(self):
        super(MyPortfolioManager, self).__init__("test_broker")

    def get_portfolio_size(self, algorithm_context: AlgorithmContext):
        pass

    def get_free_portfolio_size(self, algorithm_context: AlgorithmContext):
        pass

    def get_allocated_portfolio_size(self, algorithm_context: AlgorithmContext):
        pass

    def get_allocated_asset_size(self, asset, algorithm_context: AlgorithmContext):
        pass


class MyStrategy(Strategy):
    cycles = 0

    def on_raw_data(self, data, algorithm_context):
        MyStrategy.cycles += 1
        algorithm_context.perform_limit_order('test_broker', 'btc', 10, 10, 10)


class MyInitializer(AlgorithmContextInitializer):

    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        pass


class TestAlgorithmContext(TestCase):

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

    def test_data_provider_id_creation(self) -> None:
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

    def test_running(self) -> None:
        context = AlgorithmContext(
            data_providers=[MyDataProvider()],
            order_executors=[MyOrderExecutor()],
            portfolio_managers=[MyPortfolioManager()],
            cycles=1
        )

        context.start()
        self.assertEqual(1, MyDataProvider.cycles)

        # context = AlgorithmContext(
        #     [MyDataProvider()], random_string(10), cycles=2
        # )
        # context.start()
        # self.assertEqual(3, MyDataProvider.cycles)


class TestContextInitialization(TestCase):

    def test_initializer_registration(self) -> None:
        initializer = MyInitializer()
        context = AlgorithmContext(
            [MyDataProvider()], random_string(10), initializer
        )
        self.assertIsNotNone(context.initializer)
        self.assertEqual(initializer, context.initializer)

        context = AlgorithmContext([MyDataProvider()], random_string(10))
        context.set_algorithm_context_initializer(initializer)

        self.assertIsNotNone(context.initializer)
        self.assertEqual(initializer, context.initializer)

        with self.assertRaises(AssertionError) as exc_info:
            context = AlgorithmContext([MyDataProvider()], random_string(10))
            context.set_algorithm_context_initializer(MyInitializer)

        self.assertEqual(
            'Initializer must be an instance of AlgorithmContextInitializer',
            str(exc_info.exception)
        )

    def test_config_registration(self) -> None:
        config = AlgorithmContextConfiguration()
        context = AlgorithmContext(
            [MyDataProvider()], random_string(10),
            config=config
        )
        self.assertIsNotNone(context.config)
        self.assertEqual(config, context.config)
