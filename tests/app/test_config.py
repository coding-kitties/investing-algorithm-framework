# from unittest import TestCase

# from investing_algorithm_framework import create_app
# from investing_algorithm_framework.domain import RESOURCE_DIRECTORY
# from tests.resources import random_string

# TEST_VALUE = random_string(10)


# class TestConfig(TestCase):
#     ATTRIBUTE_ONE = "ATTRIBUTE_ONE"

#     def test_config(self):
#         app = create_app(
#             config={self.ATTRIBUTE_ONE: self.ATTRIBUTE_ONE}
#         )
#         app.initialize_config()
#         self.assertIsNotNone(app.config)
#         self.assertIsNotNone(app.config[self.ATTRIBUTE_ONE])

#     def test_resource_directory_exists(self):
#         app = create_app()
#         app.initialize_config()
#         self.assertIsNotNone(app.config)
#         self.assertIsNotNone(app.config[RESOURCE_DIRECTORY])
