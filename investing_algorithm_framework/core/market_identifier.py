from .exceptions import OperationalException


class MarketIdentifier:
    market = None

    def __init__(self, market: str = None):

        if self.market is None:
            self.market = market

        # If ID is none generate a new unique ID
        if self.market is None:
            raise OperationalException(
                f"{self.__class__.__name__} has no market specified"
            )

    def get_market(self) -> str:
        assert getattr(self, 'market', None) is not None, (
            "{} should either include an market attribute, or override "
            "the `get_market()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'market')
