from unittest import TestCase

from investing_algorithm_framework import Task, AppHook
from investing_algorithm_framework.app.algorithm import AlgorithmFactory, \
    Algorithm
from tests.resources.strategies_for_testing.strategy_v1 import \
    CrossOverStrategyV1


class TestTask(Task):

    def run(self, algorithm):
        pass

class TestAppHook(AppHook):

    def on_run(self, context) -> None:
        pass

class Test(TestCase):

    def test_with_default_params(self):
        algorithm = AlgorithmFactory.create_algorithm()
        self.assertIsInstance(algorithm, Algorithm)
        self.assertIsNotNone(algorithm.name)
        self.assertEqual(algorithm.strategies, [])
        self.assertEqual(algorithm.tasks, [])
        self.assertEqual(algorithm.on_strategy_run_hooks, [])
        self.assertEqual(algorithm.data_sources, [])

    def test_with_algorithm_param(self):
        algorithm = AlgorithmFactory.create_algorithm(
            algorithm=Algorithm(name="TestAlgorithm"),
        )
        algorithm.add_strategy(CrossOverStrategyV1)
        algorithm.add_task(TestTask())
        algorithm.add_on_strategy_run_hook(TestAppHook())

        self.assertIsInstance(algorithm, Algorithm)
        self.assertEqual(algorithm.name, "TestAlgorithm")
        self.assertEqual(len(algorithm.strategies), 1)
        self.assertEqual(len(algorithm.tasks), 1)
        self.assertEqual(len(algorithm.on_strategy_run_hooks), 1)
        self.assertEqual(len(algorithm.strategies[0].data_sources), 1)

    def test_with_strategy_param(self):
        algorithm = AlgorithmFactory.create_algorithm(
            strategy=CrossOverStrategyV1
        )
        self.assertIsInstance(algorithm, Algorithm)
        self.assertEqual(algorithm.name, "CrossOverStrategyV1")
        self.assertEqual(len(algorithm.strategies), 1)
        self.assertEqual(len(algorithm.tasks), 0)
        self.assertEqual(len(algorithm.on_strategy_run_hooks), 0)
        self.assertEqual(len(algorithm.strategies[0].data_sources), 2)
