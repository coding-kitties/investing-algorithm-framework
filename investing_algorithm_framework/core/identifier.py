from .exceptions import OperationalException


class Identifier:
    identifier = None
    RESERVED = [
        "BINANCE"
    ]

    def __init__(self, identifier: str = None, throw_exception=True):

        if self.identifier is None:
            self.identifier = identifier

        # If ID is none generate a new unique ID
        if self.identifier is None and throw_exception:
            raise OperationalException(
                f"{self.__class__.__name__} has no identifier specified"
            )

    def get_id(self, throw_exception=True) -> str:
        value = getattr(self, 'identifier', None)

        if value is None and throw_exception:
            raise OperationalException(
                f"{self.__class__.__name__} should either include an "
                f"identifier attribute, or override the `get_id()`, method."
            )

        return getattr(self, 'identifier')
