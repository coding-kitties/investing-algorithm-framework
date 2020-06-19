import os

import investing_algorithm_framework.tests.resources.standard_settings


class BaseTestMixin:

    @staticmethod
    def initialize_environment():
        os.environ.setdefault(
            'INVESTING_BOT_FRAMEWORK_SETTINGS_MODULE', 'investing_algorithm_framework.tests.resources.standard_settings'
        )

