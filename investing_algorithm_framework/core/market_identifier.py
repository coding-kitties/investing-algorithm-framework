from .exceptions import OperationalException


class MarketIdentifier:
    market = None

    def __init__(self, market: str = None):

        if self.market is None:
            self.market = market

        if self.market is None:
            raise OperationalException(
                f"{self.__class__.__name__} has no market specified"
            )

    def get_market(self, throw_exception=True) -> str:
        value = getattr(self, 'market', None)

        if value is None and throw_exception:
            raise OperationalException(
                f"{self.__class__.__name__} should either include an market "
                f"attribute, or override the `get_market()`, method."
            )

        return value
