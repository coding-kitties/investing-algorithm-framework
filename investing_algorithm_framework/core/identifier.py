from .exceptions import OperationalException


class Identifier:
    identifier = None

    def __init__(self, identifier: str = None):

        if self.identifier is None:
            self.identifier = identifier

        # If ID is none generate a new unique ID
        if self.identifier is None:
            raise OperationalException(
                f"{self.__class__.__name__} has no identifier specified"
            )

    def get_id(self) -> str:
        assert getattr(self, 'identifier', None) is not None, (
            "{} should either include an identifier attribute, or override "
            "the `get_id()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'identifier')
