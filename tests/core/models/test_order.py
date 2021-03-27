import os
from unittest import TestCase
from investing_algorithm_framework import AlgorithmContext


class TestOrderModel(TestCase):

    def __init__(self):
        super(TestOrderModel, self).__init__()

    def test_order_creation(self):

        resources = os.path.dirname(os.path.realpath(__file__))
        print(resources)
        # algorithm_context = AlgorithmContext(
        #     resources_directory=os.path.join()
        # )


