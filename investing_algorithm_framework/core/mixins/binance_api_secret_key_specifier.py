from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.configuration.constants import \
    BINANCE_API_KEY, BINANCE_SECRET_KEY


class BinanceApiSecretKeySpecifierMixin:
    binance_api_key = None
    binance_secret_key = None

    def get_secret_key(self, throw_exception=True):
        secret_key = getattr(self, BINANCE_SECRET_KEY, None)

        if secret_key is None and throw_exception:
            raise OperationalException(
                f"Binance secret key is not set on class "
                f"{self.__class__.__name__}. "
                f"Either override 'get_secret_key' method or set "
                f"the 'secret_key' attribute in the algorithm config."
            )

        return secret_key

    def get_api_key(self, throw_exception=True):
        api_key = getattr(self, BINANCE_API_KEY, None)

        if api_key is None and throw_exception:
            raise OperationalException(
                "Binance api key is not set. Either override 'get_api_key' "
                "method or set the 'binance_api_key' attribute in the "
                "algorithm config."
            )

        return api_key
