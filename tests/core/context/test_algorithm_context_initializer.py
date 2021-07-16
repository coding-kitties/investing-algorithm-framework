from investing_algorithm_framework.core.context import AlgorithmContext
from tests.resources.test_base import TestBase
from investing_algorithm_framework import AlgorithmContextInitializer


class Initializer(AlgorithmContextInitializer):

    def initialize(self, algorithm: AlgorithmContext) -> None:
        TestAlgorithmContextInitialization.initialize_has_run += 1


class TestAlgorithmContextInitialization(TestBase):
    initialize_has_run = 0

    def setUp(self) -> None:
        super(TestAlgorithmContextInitialization, self).setUp()
        TestAlgorithmContextInitialization.initialize_has_run = 0
        self.algo_app.algorithm.add_initializer(Initializer())
        self.algo_app.algorithm.start()

    def test(self):
        self.assertEqual(
            1, TestAlgorithmContextInitialization.initialize_has_run
        )
        self.algo_app.algorithm.stop()
        self.algo_app.algorithm.start()
        self.assertEqual(
            1, TestAlgorithmContextInitialization.initialize_has_run
        )
