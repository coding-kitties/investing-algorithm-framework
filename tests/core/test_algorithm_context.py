from unittest import TestCase

from investing_algorithm_framework.core.context import AlgorithmContext, \
    AlgorithmContextInitializer, AlgorithmContextConfiguration
from investing_algorithm_framework.core.data_providers import DataProvider
from tests.resources.utils import random_string


class MyDataProvider(DataProvider):
    cycles = 0

    def get_data(self, algorithm_context: AlgorithmContext):
        MyDataProvider.cycles += 1
        return 'data'


class MyInitializer(AlgorithmContextInitializer):

    def initialize(self, algorithm_context: AlgorithmContext) -> None:
        pass


class TestAlgorithmContext(TestCase):

    def test_data_provider_registration(self) -> None:
        context = AlgorithmContext([MyDataProvider()])
        self.assertIsNotNone(context)
        self.assertIsNotNone(context.data_providers)
        self.assertEqual(1, len(context.data_providers))

        with self.assertRaises(Exception) as exc_info:
            AlgorithmContext([MyDataProvider], random_string(10))

        self.assertEqual(
            str(exc_info.exception),
            "Data provider must be an instance "
            "of the AbstractDataProvider class"
        )

    def test_data_provider_id_creation(self) -> None:
        context = AlgorithmContext([MyDataProvider()])
        self.assertIsNotNone(context.algorithm_id)

    def test_running(self) -> None:
        context = AlgorithmContext(
            [MyDataProvider()], random_string(10), cycles=1
        )
        context.start()
        self.assertEqual(1, MyDataProvider.cycles)

        context = AlgorithmContext(
            [MyDataProvider()], random_string(10), cycles=2
        )
        context.start()
        self.assertEqual(3, MyDataProvider.cycles)


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
