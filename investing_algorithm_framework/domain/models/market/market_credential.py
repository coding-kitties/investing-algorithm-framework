import os
import logging

from investing_algorithm_framework.domain import OperationalException

logger = logging.getLogger("investing_algorithm_framework")


class MarketCredential:
    """
    Market credential model to store the api key and secret key for a market.
    """
    def __init__(
        self, market: str, api_key: str = None, secret_key: str = None
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._market = market

    def initialize(self):
        """
        Internal helper to initialize the market credential.
        """
        logger.info(f"Initializing market credential for {self.market}")

        if self.api_key is None:
            logger.info(
                "Reading api key from environment variable"
                f" {self.market.upper()}_API_KEY"
            )

            # Check if environment variable is set
            environment_variable = f"{self.market.upper()}_API_KEY"
            self._api_key = os.getenv(environment_variable)

            if self.api_key is None:
                raise OperationalException(
                    f"Market credential for market {self.market}"
                    " requires an api key, either"
                    " as an argument or as an environment variable"
                    f" named as {self._market.upper()}_API_KEY"
                )

        if self.secret_key is None:
            logger.info(
                "Reading secret key from environment variable"
                f" {self.market.upper()}_SECRET_KEY"
            )

            # Check if environment variable is set
            environment_variable = f"{self.market.upper()}_SECRET_KEY"
            self._secret_key = os.getenv(environment_variable)

    def get_api_key(self):
        return self.api_key

    def get_secret_key(self):
        return self.secret_key

    def get_market(self):
        return self.market

    @property
    def market(self):
        return self._market

    @market.setter
    def market(self, market):
        self._market = market

    @property
    def api_key(self):
        return self._api_key

    @property
    def secret_key(self):
        return self._secret_key

    def __repr__(self):
        return f"MarketCredential(" \
               f"{self.market}, {self.api_key}, {self.secret_key}"
