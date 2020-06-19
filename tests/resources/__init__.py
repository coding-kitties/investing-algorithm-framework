import os

import tests.resources.standard_settings


class BaseTestMixin:

    @staticmethod
    def initialize_environment():
        os.environ.setdefault(
            'INVESTING_BOT_FRAMEWORK_SETTINGS_MODULE', 'tests.resources.standard_settings'
        )

