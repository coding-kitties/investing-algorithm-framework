import inspect
import os

from investing_algorithm_framework.configuration.constants import \
    CCXT_ENABLED, MARKET, DATABASE_DIRECTORY_PATH, DATABASE_NAME, \
    DATABASE_CONFIG, RESOURCE_DIRECTORY, APPLICATION_CONFIGURED, \
    SQLALCHEMY_DATABASE_URI, LOG_LEVEL, SQLITE_ENABLED, PORTFOLIOS, \
    SQLITE_INITIALIZED, SQLALCHEMY_INITIALIZED
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.portfolio_managers\
    .sqllite_portfolio_manager import SQLLitePortfolioManager


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
        track_from=None,
        check_api_key_specification=True,
        check_secret_key_specification=True,
        check_trading_symbol=True,
        check_market=True
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

        if check_api_key_specification and self.api_key is None:
            raise OperationalException(
                "Api key not specified in portfolio configuration"
            )

        if check_secret_key_specification and self.secret_key is None:
            raise OperationalException(
                "Secret key not specified in portfolio configuration"
            )

        if check_trading_symbol and self.trading_symbol is None:
            raise OperationalException(
                "Trading symbol not specified in portfolio configuration"
            )

        if check_market and self.market is None:
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
            track_from=data.get("TRACK_FROM", None),
            sqlite=data.get("SQLITE", True),
            check_api_key_specification=data.get("CHECK_API_KEY", True),
            check_secret_key_specification=data.get("CHECK_SECRET_KEY", True),
            check_trading_symbol=data.get("CHECK_TRADING_SYMBOL", True),
            check_market=data.get("CHECK_MARKET", True)
        )

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def to_string(self):
        return self.repr(
            identifier=self.get_identifier(),
            sqlite=self.get_sqlite()
        )

    def __repr__(self):
        return self.to_string()


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

    def sqlite_enabled(self):
        sqlite = self.config.get(SQLITE_ENABLED)
        return sqlite is not None and sqlite

    def sqlite_required(self):
        portfolio_configurations = self.get_portfolio_configurations()

        if portfolio_configurations is None:
            return False

        sqlite_portfolios = [
            portfolio_configuration for portfolio_configuration
            in portfolio_configurations if portfolio_configuration.get_sqlite()
        ]

        return len(sqlite_portfolios) > 0

    def sqlite_configured(self):

        if SQLITE_INITIALIZED not in self.config:
            return False

        return self.config[SQLITE_INITIALIZED]

    def set_sqlite_configured(self):
        self.config[SQLITE_INITIALIZED] = True

    def resource_directory_configured(self):
        resource_directory = self.config.get(RESOURCE_DIRECTORY, None)
        return resource_directory is not None

    def set_resource_directory(self, resource_directory):
        self.config[RESOURCE_DIRECTORY] = resource_directory

    def can_write_to_resource_directory(self):

        if not self.resource_directory_configured():
            return False

        resource_directory = self.config.get(RESOURCE_DIRECTORY, None)

        if not os.path.isdir(resource_directory):
            return False

        return os.access(resource_directory, os.W_OK)

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

    def load(self, config):

        if inspect.isclass(config):
            config = config()

        assert isinstance(config, dict), (
            "Provided configuration is not of type Dict"
        )

        self.config = config

        if LOG_LEVEL not in self.config:
            self.config[LOG_LEVEL] = "INFO"

    def get(self, key, default=None):
        return self.config.get(key, default)

    def get_portfolio_configurations(self):
        portfolio_configurations = []

        if PORTFOLIOS in self.config:

            for key in self.config[PORTFOLIOS]:
                portfolio_data = self.config[PORTFOLIOS][key]
                portfolio_data["identifier"] = key

                portfolio_configurations.append(
                    PortfolioConfiguration
                        .from_dict(portfolio_data)
                )

        return portfolio_configurations

    def application_configured(self):

        if APPLICATION_CONFIGURED not in self.config:
            return False

        return self.config[APPLICATION_CONFIGURED]

    def set_application_configured(self):
        self.config[APPLICATION_CONFIGURED] = True

    def sql_alchemy_configured(self):

        if SQLALCHEMY_INITIALIZED not in self.config:
            return False

        return self.config[SQLALCHEMY_INITIALIZED]

    def set_sql_alchemy_configured(self):
        self.config[SQLALCHEMY_INITIALIZED] = True

    def get_database_config(self):

        if DATABASE_CONFIG not in self.config:
            return None

        return self.config[DATABASE_CONFIG]

    def add_portfolio_configuration(self, portfolio_managers):

        if PORTFOLIOS not in self.config:
            self.config[PORTFOLIOS] = {}

        portfolio_configurations = self.config[PORTFOLIOS]

        for portfolio_manager in portfolio_managers:
            if portfolio_manager.identifier not in portfolio_configurations:
                portfolio_configurations[portfolio_manager.identifier] = {
                    "SQLITE": isinstance(
                        portfolio_manager, SQLLitePortfolioManager
                    ),
                    "CHECK_API_KEY": False,
                    "CHECK_SECRET_KEY": False,
                    "CHECK_MARKET": False,
                    "CHECK_TRADING_SYMBOL": False,
                    "CCXT": False
                }

        self.config[PORTFOLIOS] = portfolio_configurations
