from tests.resources.test_base import TestBase
from investing_algorithm_framework.extensions import scheduler
from investing_algorithm_framework import TimeUnit


def test_func(_):
    TestAlgorithmStop.test_func_has_run = True


class TestAlgorithmStop(TestBase):
    test_func_has_run = False

    def setUp(self):
        super(TestAlgorithmStop, self).setUp()
        self.algo_app.algorithm.schedule(
            test_func, time_unit=TimeUnit.SECONDS, interval=1
        )
        TestAlgorithmStop.test_func_has_run = False
        self.start_algorithm()

    def test_stop(self):
        self.algo_app.algorithm.start()
        self.assertFalse(TestAlgorithmStop.test_func_has_run)
        response = self.client.get("/stop")
        self.assertEqual(200, response.status_code)
        self.assertFalse(self.algo_app.algorithm.running)
        self.assertFalse(TestAlgorithmStop.test_func_has_run)
        self.assertEqual(0, len(scheduler.get_jobs()))
        self.algo_app.algorithm.stop()

    def test_stop_with_already_stopped_algorithm(self):
        self.algo_app.algorithm.start()
        self.assertFalse(TestAlgorithmStop.test_func_has_run)
        response = self.client.get("/stop")
        self.assertEqual(200, response.status_code)
        self.assertFalse(self.algo_app.algorithm.running)

        response = self.client.get("/stop")
        self.assertEqual(400, response.status_code)
        self.assertFalse(self.algo_app.algorithm.running)
        self.assertEqual(0, len(scheduler.get_jobs()))
        self.assertFalse(TestAlgorithmStop.test_func_has_run)
        self.algo_app.algorithm.stop()

