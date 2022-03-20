from time import sleep
from tests.resources.test_base import TestBase
from investing_algorithm_framework import TimeUnit


def test_func(_):
    TestAlgorithmStart.test_func_has_run = True


class TestAlgorithmStart(TestBase):
    test_func_has_run = False

    def setUp(self):
        super(TestAlgorithmStart, self).setUp()
        self.algo_app.algorithm.schedule(
            test_func, time_unit=TimeUnit.SECOND, interval=1
        )
        TestAlgorithmStart.test_func_has_run = False
        self.start_algorithm()

    def test_start(self):
        self.algo_app.algorithm.stop()
        self.assertFalse(TestAlgorithmStart.test_func_has_run)
        response = self.client.get("/start")
        self.assertEqual(200, response.status_code)
        self.assertTrue(self.algo_app.algorithm.running)
        sleep(2)
        self.assertTrue(TestAlgorithmStart.test_func_has_run)

    def test_start_with_already_stopped_algorithm(self):
        self.algo_app.algorithm.stop()
        self.assertFalse(TestAlgorithmStart.test_func_has_run)
        response = self.client.get("/start")
        self.assertEqual(200, response.status_code)
        self.assertTrue(self.algo_app.algorithm.running)

        response = self.client.get("/start")
        self.assertEqual(400, response.status_code)
        self.assertTrue(self.algo_app.algorithm.running)

        sleep(2)
        self.assertTrue(TestAlgorithmStart.test_func_has_run)

    def tearDown(self):
        super(TestAlgorithmStart, self).tearDown()
