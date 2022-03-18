from abc import abstractmethod, ABC
from datetime import datetime, timedelta
from logging import getLogger
from typing import List

from investing_algorithm_framework.configuration.constants import \
    TRADING_SYMBOL
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.models import OrderSide, OrderType, \
    Portfolio
from investing_algorithm_framework.core.models.order import Order, OrderStatus
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.snapshots.asset_price import \
    AssetPrice
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory

logger = getLogger(__name__)


class PortfolioManager(ABC, Identifier):
    update_minutes = 5
    
    def __init__(self, identifier=None, track_from=None, trading_symbol=None):
        super(PortfolioManager, self).__init__(identifier)

        if track_from is not None:
            self.track_from = track_from

        if identifier is not None:
            self.identifier = identifier

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol.upper()

        self.portfolio = None

    @abstractmethod
    def get_positions(
        self, algorithm_context=None, **kwargs
    ) -> List[Position]:
        pass

    @abstractmethod
    def get_orders(
        self, symbol, since: datetime = None,  algorithm_context=None, **kwargs
    ) -> List[Order]:
        pass

    @abstractmethod
    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ) -> List[AssetPrice]:
        pass

    def initialize(self, algorithm_context):
        self.create_portfolio(algorithm_context)

        logger.info(f"initializing portfolio {self.get_identifier()}")
        logger.info(
            f"Retrieving all positions for {self.get_identifier()} portfolio"
        )
        portfolio = self.get_portfolio(algorithm_context)
        positions = self.get_positions(algorithm_context=algorithm_context)
        portfolio.add_positions(positions)

        symbols = []

        # Extract all symbols of the positions
        # (target symbol and trading symbol)
        for position in portfolio.get_positions():
            symbols.append(position.get_symbol())

        logger.info(
            f"Retrieving all orders for {self.get_identifier()} portfolio"
        )

        prices = self.get_prices(
            symbols=symbols, algorithm_context=algorithm_context
        )

        for position in portfolio.get_positions():

            if position.get_target_symbol() != \
                    self.get_trading_symbol(algorithm_context):

                if self.track_from is not None:
                    orders = self.get_orders(
                        symbol=position.get_symbol(),
                        algorithm_context=algorithm_context,
                        since=datetime.strptime(self.track_from, "%d-%m-%Y")
                    )
                else:
                    orders = self.get_orders(
                        symbol=position.get_symbol(),
                        algorithm_context=algorithm_context,
                    )

                portfolio.add_orders(orders)

                matching_asset_price = next(
                    (asset_price for asset_price in prices
                     if asset_price.get_symbol() == position.get_symbol()),
                    None
                )

                # Add asset price
                if matching_asset_price is not None:
                    position.set_price(matching_asset_price.get_price())

        # Validate portfolio model
        portfolio.validate_portfolio()
        portfolio.updated()
        logger.info(f"Portfolio {self.get_identifier()} initialized")

    def create_portfolio(self, algorithm_context):
        self.portfolio = Portfolio(
            identifier=self.identifier,
            trading_symbol=self.get_trading_symbol(algorithm_context),
        )

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

    def sync_portfolio(self, algorithm_context):
        logger.info(f"Syncing portfolio {self.identifier}")
        portfolio = self.get_portfolio(algorithm_context)

        # Create a portfolio object if it not exists
        positions = self.get_positions(algorithm_context=algorithm_context)
        portfolio.add_positions(positions)

        symbols = []

        # Extract all symbols of the positions
        # (target symbol and trading symbol)
        for position in portfolio.get_positions():
            symbols.append(position.get_symbol())

        prices = self.get_prices(
            symbols=symbols, algorithm_context=algorithm_context
        )

        for position in portfolio.get_positions():

            if position.get_target_symbol() != \
                    self.get_trading_symbol(algorithm_context):
                matching_asset_price = next(
                    (asset_price for asset_price in prices
                     if asset_price.get_symbol() == position.get_symbol()),
                    None
                )

                if matching_asset_price is not None:
                    position.set_price(matching_asset_price.get_price())

                orders = self.get_orders(
                    symbol=position.get_symbol(),
                    since=datetime.utcnow() - timedelta(days=1),
                    algorithm_context=algorithm_context
                )
                portfolio.add_orders(orders)

        portfolio.updated()

    def get_portfolio(
        self,
        algorithm_context,
        update=False,
        execute_update=True,
        **kwargs
    ) -> Portfolio:
        return self.portfolio

    def requires_update(self,  algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)

        if portfolio.updated_at is None:
            return True

        return \
            (portfolio.updated_at + timedelta(minutes=self.update_minutes)) \
            < datetime.utcnow()

    def create_order(
        self,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        type=OrderType.LIMIT.value,
        side=OrderSide.BUY.value,
        algorithm_context=None
    ) -> Order:
        order = Order(
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol(algorithm_context),
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            type=type,
            side=side,
            status=OrderStatus.TO_BE_SENT.value
        )

        # Validate the order
        order_validator = OrderValidatorFactory.of(self.identifier)
        order_validator.validate(
            order, self.get_portfolio(algorithm_context=algorithm_context)
        )

        return order

    def add_order(self, order, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_order(order)

    def add_orders(self, orders, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_orders(orders)

    def add_position(self, position, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_position(position)

    def add_positions(self, positions, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)
        portfolio.add_positions(positions)
