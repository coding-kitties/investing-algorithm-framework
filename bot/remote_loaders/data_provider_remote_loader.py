import logging
from pathlib import Path

from bot.data import DataProvider
from bot import OperationalException
from bot.constants import PLUGIN_STRATEGIES_DIR, PLUGIN_DATA_PROVIDERS_DIR
from bot.remote_loaders.remote_loader import RemoteLoader

logger = logging.getLogger(__name__)


class DataProviderRemoteLoader(RemoteLoader):

    def load_data_provider(self, data_provider_class_name: str) -> DataProvider:

        logger.info("Loading remote data providers ...")

        if not data_provider_class_name:
            raise OperationalException("Provided data provider has it search class name not set")

        data_providers_dir = Path(PLUGIN_DATA_PROVIDERS_DIR)
        modules = self.locate_python_modules(data_providers_dir)
        location = self.locate_class(modules, data_provider_class_name)
        generator = self.create_class_generators(location, data_provider_class_name, DataProvider)
        instance: DataProvider = next(generator, None)()

        if instance and isinstance(instance, DataProvider):
            return instance

        raise OperationalException(
            f"Impossible to load Strategy '{data_provider_class_name}'. This data provider does not exist "
            "or contains Python code errors."
        )
