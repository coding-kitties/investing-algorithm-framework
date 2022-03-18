import os

from investing_algorithm_framework.configuration.constants import \
    CCXT_ENABLED, API_KEY, SECRET_KEY, MARKET, RESOURCES_DIRECTORY, \
    DATABASE_DIRECTORY_PATH, DATABASE_NAME, DATABASE_CONFIG, \
    SQLALCHEMY_DATABASE_URI, LOG_LEVEL, SQLITE_ENABLED, PORTFOLIOS
from investing_algorithm_framework.core.exceptions import OperationalException


class PortfolioConfiguration:

    def __init__(
        self,
            identifier,
            api_key,
            secret_key,
            trading_symbol,
            market,
            ccxt=True,
            sqlite=True,
            track_from=None
    ):
        self.identifier = identifier
        self.api_key = api_key
        self.secret_key = secret_key
        self.trading_symbol = trading_symbol
        self.market = market
        self.ccxt = ccxt
        self.sqlite = sqlite
        self.track_from = track_from

        if self.identifier is None:
            raise OperationalException(
                "Identifier not specified in portfolio configuration"
            )

        if self.api_key is None:
            raise OperationalException(
                "Api key not specified in portfolio configuration"
            )

        if self.secret_key is None:
            raise OperationalException(
                "Secret key not specified in portfolio configuration"
            )

        if self.trading_symbol is None:
            raise OperationalException(
                "Trading symbol not specified in portfolio configuration"
            )

        if self.market is None:
            raise OperationalException(
                "Market not specified in portfolio configuration"
            )

    def get_identifier(self):
        return self.identifier

    def get_api_key(self):
        return self.api_key

    def get_secret_key(self):
        return self.secret_key

    def get_trading_symbol(self):
        return self.trading_symbol

    def get_ccxt_enabled(self):
        return self.ccxt

    def get_market(self):
        return self.market

    def get_sqlite(self):
        return self.sqlite

    def get_track_from(self):
        return self.track_from

    @staticmethod
    def from_dict(data):
        return PortfolioConfiguration(
            identifier=data.get("identifier"),
            api_key=data.get("API_KEY"),
            secret_key=data.get("SECRET_KEY"),
            trading_symbol=data.get("TRADING_SYMBOL"),
            ccxt=data.get("CCXT", True),
            market=data.get("MARKET"),
            track_from=data.get("TRACK_FROM", None)
        )


class AlgorithmContextConfiguration:
    """
    Base wrapper for Config module. It will load all the
    default settings for a given settings module and will allow for run time
    specification
    """
    config = {}

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

        if DATABASE_CONFIG not in self.config:
            self.config[DATABASE_CONFIG] = {}

        self.config[DATABASE_CONFIG][DATABASE_NAME] = name

    def set_database_directory(self, database_directory):

        if DATABASE_CONFIG not in self.config:
            self.config[DATABASE_CONFIG] = {}

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

    def validate_database_configuration(self):
        database_config = self.config.get(DATABASE_CONFIG)

        if database_config is None:
            raise OperationalException(
                "Database configuration is not configured"
            )

        database_directory = database_config.get(DATABASE_DIRECTORY_PATH)
        database_name = database_config.get(DATABASE_NAME)
        sqlalchemy_uri = self.config.get(SQLALCHEMY_DATABASE_URI)

        if database_directory is None:
            raise OperationalException(
                f"{DATABASE_DIRECTORY_PATH} is not set in config"
            )

        if database_name is None:
            raise OperationalException(
                f"{DATABASE_NAME} is not set in config"
            )

        if sqlalchemy_uri is None:
            raise OperationalException(
                f"{SQLALCHEMY_DATABASE_URI} is not set in config"
            )

    def sqlite_enabled(self):
        return self.config.get(SQLITE_ENABLED, False)

    def load(self, config):
        self.config = config

        if LOG_LEVEL not in self.config:
            self.config[LOG_LEVEL] = "INFO"

    def get(self, key, default=None):
        return self.config.get(key, default)

    def get_portfolios(self):
        portfolio_configurations = []

        if PORTFOLIOS in self.config:
            for key in self.config[PORTFOLIOS]:
                data = {"identifier": key}
                data.update(self.config[PORTFOLIOS][key])

                portfolio_configurations.append(
                    PortfolioConfiguration.from_dict(data)
                )

        return portfolio_configurations
