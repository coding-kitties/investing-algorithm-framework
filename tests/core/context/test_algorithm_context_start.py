from tests.resources import TestBase
from investing_algorithm_framework import TimeUnit
from investing_algorithm_framework.extensions import scheduler


def worker_one(algorithm):
    pass


def worker_two(algorithm):
    pass


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()
        self.algo_app.algorithm.schedule(worker_one, None, TimeUnit.SECONDS, 1)
        self.algo_app.algorithm.schedule(worker_two, None, TimeUnit.SECONDS, 1)
        self.algo_app.algorithm.start()

    def test_start_context(self) -> None:
        self.assertTrue(self.algo_app.algorithm.running)
        self.assertEqual(2, len(scheduler.get_jobs()))
        self.algo_app.stop_algorithm()
        self.assertFalse(self.algo_app.algorithm.running)
        self.assertEqual(0, len(scheduler.get_jobs()))
        self.algo_app.start_algorithm()
        self.assertTrue(self.algo_app.algorithm.running)
        self.assertEqual(2, len(scheduler.get_jobs()))