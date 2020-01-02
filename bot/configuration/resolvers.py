from typing import Dict, Any, List

from bot.strategies import Strategy
from bot.data import DataProvider
from bot import DependencyException, OperationalException
from bot.remote_loaders import StrategyRemoteLoader, DataProviderRemoteLoader


def get_data_provider_configurations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    data_provider_configurations = config.get('data_providers', {})

    entries = []

    if not data_provider_configurations:
        raise DependencyException(
            "Could not resolve data providers, please provide the data provider configurations in your config file. "
            "You could also use de default data providers, that can be found in the data/data_provider/templates"
            " directory. If you have difficulties creating your own data provider, please see the documentation"
        )

    for data_provider_entry in data_provider_configurations.keys():
        entry = {
            'key': data_provider_entry,
            'class_name': data_provider_configurations[data_provider_entry].get('class_name', None),
            'enabled': bool(data_provider_configurations[data_provider_entry].get('enabled', False)),
            'plugin': bool(data_provider_configurations[data_provider_entry].get('plugin', False))
        }
        entries.append(entry)

    return entries


def get_strategy_configurations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    strategy_configurations = config.get('strategies', {})

    entries = []

    if not strategy_configurations:
        raise DependencyException(
            "Could not resolve strategies, please provide the strategy configurations in your config file. "
            "You could also use de default strategies, that can be found in the "
            "strategies/strategy/templates directory. If you have difficulties creating "
            "your own strategies, please see the documentation"
        )

    for strategy_entry in strategy_configurations.keys():
        entry = {
            'key': strategy_entry,
            'class_name': strategy_configurations[strategy_entry].get('class_name', None),
            'enabled': bool(strategy_configurations[strategy_entry].get('enabled', False)),
            'plugin': bool(strategy_configurations[strategy_entry].get('plugin', False))
        }
        entries.append(entry)

    return entries


def get_data_provider_plugins(data_provider_configurations: List[Dict[str, Any]]) -> List[DataProvider]:
    remote_loader = DataProviderRemoteLoader()
    data_providers = []

    for entry in data_provider_configurations:

        if not entry.get('enabled', False):
            continue

        if not entry.get('key', None):
            raise DependencyException("Configured data provider must specify a identifier name")

        if not entry.get('class_name', None):
            raise DependencyException(
                "Configured data provider {} must specify a class name corresponding "
                "to the data provider implementation".format(entry)
            )

        if not bool(entry.get('plugin', False)):
            continue

        data_provider: DataProvider = remote_loader.load_data_provider(entry.get('class_name'))
        data_providers.append(data_provider)

    return data_providers


def get_data_provider_templates(data_provider_configurations: List[Dict[str, Any]]) -> List[DataProvider]:
    data_providers = []

    for entry in data_provider_configurations:

        if not entry.get('key', None):
            raise DependencyException("Configured data provider must specify a identifier name")

        if bool(entry.get('plugin', False)):
            continue

        if entry.get("key") == "":
            continue

        # data_provider: DataProvider = remote_loader.load_data_provider(entry.get('class_name'))
        # data_providers.append(data_provider)

    return None


def get_strategy_plugins(strategy_configurations: List[Dict[str, Any]]) -> List[Strategy]:
    remote_loader = StrategyRemoteLoader()
    strategies = []

    for entry in strategy_configurations:

        if not entry.get('enabled', False):
            continue

        if not entry.get('key', None):
            raise DependencyException("Configured strategy must specify a identifier name")

        if not entry.get('class_name', None):
            raise DependencyException(
                "Configured strategy {} must specify a class name corresponding "
                "to the strategy implementation".format(entry)
            )

        if not bool(entry.get('plugin', False)):
            continue

        strategy: Strategy = remote_loader.load_strategy(entry.get('class_name'))
        strategies.append(strategy)

    return strategies


def get_strategy_templates(strategy_configurations: List[Dict[str, Any]]) -> List[Strategy]:
    strategies = []

    for entry in strategy_configurations:

        if not entry.get('key', None):
            raise DependencyException("Configured data provider must specify a identifier name")

        if bool(entry.get('plugin', False)):
            continue

        if entry.get("key") == "":
            continue

        # data_provider: DataProvider = remote_loader.load_data_provider(entry.get('class_name'))
        # data_providers.append(data_provider)

    return None



