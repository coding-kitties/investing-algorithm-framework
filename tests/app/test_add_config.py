import os
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY


class Test(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_add(self):
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.config.get("test"))
        self.assertIsNotNone(app.config.get(RESOURCE_DIRECTORY))
