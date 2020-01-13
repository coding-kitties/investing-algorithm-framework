from typing import Dict, Any, List

from bot.data import DataProvider
from bot.constants import TimeUnit
from bot import DependencyException
from bot.remote_loaders import DataProviderRemoteLoader


def get_data_provider_configurations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Function that validates and loads all the data provider definitions for the given configuration
    """
    data_providers_configuration = config.get('data_providers', None)

    if data_providers_configuration is None:
        raise DependencyException("Data providers are not defined in the config. Please make sure that you "
                                  "define some data providers. If you have difficulties creating a data provider, "
                                  "please see the documentation for examples.")

    for data_provider_config in data_providers_configuration:

        assert data_provider_config.get('class_name', None) is not None, (
            "Expected data provider to define a class_name. Please fix your data provider configuration."
        )

        assert data_provider_config.get('schedule', None) is not None, (
            "Expected data provider {} to define an schedule. Please fix your data provider "
            "configuration.".format(data_provider_config.get('class_name'))
        )

        if not TimeUnit.ALWAYS.equals(data_provider_config.get('schedule')):

            assert data_provider_config.get('schedule').get('time_unit', None) is not None, (
                "Expected data provider {} to define an schedule time_unit. Please fix your data provider "
                "configuration.".format(data_provider_config.get('class_name'))
            )

            assert data_provider_config.get('schedule').get('interval', None) is not None, (
                "Expected data provider {} to define an schedule interval. Please fix your data provider "
                "configuration.".format(data_provider_config.get('class_name'))
            )

        assert data_provider_config.get('plugin', None) is not None, (
            "Expected provider for data provider {} to define plugin flag. Please fix your data provider "
            "configuration. If you make use of one of the templates set the flag to "
            "false.".format(data_provider_config.get('class_name'))
        )

    return data_providers_configuration


def load_data_provider(data_provider_configuration: Dict[str, str]) -> DataProvider:

    class_name = data_provider_configuration.get('class_name')
    plugin = bool(data_provider_configuration.get('plugin'))
    data_provider: DataProvider = None

    if plugin:
        remote_loader = DataProviderRemoteLoader()
        return remote_loader.load_data_provider(class_name)
    else:
        return None




