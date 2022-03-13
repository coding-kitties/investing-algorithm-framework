import os

from investing_algorithm_framework.configuration.constants import \
    CCXT_ENABLED, API_KEY, SECRET_KEY, MARKET, RESOURCES_DIRECTORY, \
    DATABASE_DIRECTORY_PATH, DATABASE_NAME, DATABASE_CONFIG, \
    SQLALCHEMY_DATABASE_URI


class AlgorithmContextConfiguration:
    """
    Base wrapper for Config module. It will load all the
    default settings for a given settings module and will allow for run time
    specification
    """
    config = None

    def ccxt_enabled(self):
        return self.config.get(CCXT_ENABLED, False) \
               and self.config.get(MARKET, None) is not None

    def ccxt_authentication_configured(self):
        api_key = self.config.get(API_KEY, None)
        secret_key = self.config.get(SECRET_KEY, None)
        return self.ccxt_enabled() and api_key is not None \
            and secret_key is not None

    def resource_directory_configured(self):
        resource_directory = self.config.get(RESOURCES_DIRECTORY, None)
        return resource_directory is not None

    def set_resource_directory(self, resource_directory):
        self.config[RESOURCES_DIRECTORY] = resource_directory

    def set_database_name(self, name):
        self.config[DATABASE_CONFIG][DATABASE_NAME] = name

    def set_database_directory(self, database_directory):
        self.config[DATABASE_CONFIG][DATABASE_DIRECTORY_PATH] \
            = database_directory

    def set_sql_alchemy_uri(self, sqlalchemy_uri):
        self.config[SQLALCHEMY_DATABASE_URI] = sqlalchemy_uri

    def can_write_to_resource_directory(self):

        if not self.resource_directory_configured():
            return False

        resource_directory = self.config.get(RESOURCES_DIRECTORY, None)

        if not os.path.isdir(resource_directory):
            return False

        return os.access(resource_directory, os.W_OK)

    def load(self, config):
        self.config = config

    def get(self, key, default=None):
        return self.config.get(key, default)
