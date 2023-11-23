from investing_algorithm_framework.domain import Config


class ConfigurationService:

    def __init__(self):
        self._config = Config()

    @property
    def config(self):
        return self._config

    def get_config(self):
        return self._config

    def set_config(self, config):
        self._config = config

    def add_value(self, key, value):
        self._config.set(key, value)

    def get_value(self, key):
        return self._config.get(key)

    def remove_value(self, key):
        self._config.pop(key)

    def initialize_from_dict(self, data):
        self._config = Config.from_dict(data)
