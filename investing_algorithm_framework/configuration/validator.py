import logging
from investing_algorithm_framework.core.exceptions import ImproperlyConfigured
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, LOG_LEVEL, RESOURCES_DIRECTORY

logger = logging.getLogger(__name__)


class ConfigValidator:
    required_variables = [
        DATABASE_CONFIG,
        RESOURCES_DIRECTORY,
        LOG_LEVEL
    ]

    @staticmethod
    def validate(config):
        logger.info("Validating application configuration")

        for variable in ConfigValidator.required_variables:

            if variable not in config or config.get(variable, None) is None:
                raise ImproperlyConfigured(
                    "{} is not set".format(variable)
                )
