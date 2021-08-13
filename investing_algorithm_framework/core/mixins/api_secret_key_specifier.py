from investing_algorithm_framework.core.exceptions import OperationalException


class ApiSecretKeySpecifierMixin:
    api_key = None
    secret_key = None

    def get_secret_key(self):
        secret_key = getattr(self, "secret_key", None)

        if secret_key is None:
            raise OperationalException(
                f"Secret key is not set on class {self.__class__.__name__}. "
                f"Either override 'get_secret_key' method or set "
                f"the 'secret_key' attribute."
            )

        return secret_key

    def get_api_key(self):
        api_key = getattr(self, "api_key", None)

        if api_key is None:
            raise OperationalException(
                "Api key is not set. Either override 'get_api_key' "
                "method or set the 'api_key' attribute."
            )

        return api_key
