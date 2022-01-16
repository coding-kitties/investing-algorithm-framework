from abc import abstractmethod, ABC

from investing_algorithm_framework.configuration.constants import \
    TRADING_SYMBOL
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.market_identifier import \
    MarketIdentifier
from investing_algorithm_framework.core.models import OrderSide, OrderType


class PortfolioManager(ABC, Identifier, MarketIdentifier):
    trading_symbol = None

    @abstractmethod
    def get_unallocated(self, algorithm_context, sync=False):
        pass

    @abstractmethod
    def get_allocated(self, algorithm_context, sync=False):
        pass

    @abstractmethod
    def initialize(self, algorithm_context):
        pass

    @abstractmethod
    def get_portfolio(self, algorithm_context):
        pass

    def get_trading_symbol(self, algorithm_context) -> str:
        trading_symbol = getattr(self, "trading_symbol", None)

        if trading_symbol is None:
            trading_symbol = algorithm_context.config.get(TRADING_SYMBOL, None)

        if trading_symbol is None:
            raise OperationalException(
                "Trading symbol is not set. Either override "
                "'get_trading_symbol' method or set "
                "the 'trading_symbol' attribute in the algorithm config."
            )

        return trading_symbol

    @abstractmethod
    def get_positions(self, symbol: str = None, lazy=False):
        pass

    @abstractmethod
    def get_orders(self, symbol: str = None, status=None, lazy=False):
        pass

    @abstractmethod
    def create_order(
        self,
        symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_type=OrderType.LIMIT.value,
        order_side=OrderSide.BUY.value,
        context=None,
        validate_pair=True
    ):
        pass

    @abstractmethod
    def add_order(self, order):
        pass
