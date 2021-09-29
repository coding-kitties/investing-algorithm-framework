from abc import abstractmethod, ABC

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.market_identifier import \
    MarketIdentifier
from investing_algorithm_framework.core.models import Position, Order, \
    Portfolio, db, OrderSide
from investing_algorithm_framework import current_app


class PortfolioManager(ABC, Identifier, MarketIdentifier):
    trading_currency = None

    @abstractmethod
    def get_initial_unallocated_size(self):
        pass

    def initialize(self, algorithm_context):
        self._initialize_portfolio()

    def _initialize_portfolio(self):
        portfolio = self.get_portfolio()

        if portfolio is None:
            portfolio = Portfolio(
                identifier=self.identifier,
                trading_symbol=self.trading_currency,
                unallocated=self.get_initial_unallocated_size(),
                market=self.get_market()
            )
            portfolio.save(db)

    def get_portfolio(self) -> Portfolio:
        return Portfolio.query.filter_by(identifier=self.identifier).first()

    @property
    def unallocated(self):
        return self.get_portfolio().unallocated

    def get_trading_symbol(self) -> str:

        trading_symbol = getattr(self, "trading_symbol", None)

        if trading_symbol is None:
            raise OperationalException(
                "Trading symbol is not set. Either override "
                "'get_trading_symbol' method or set "
                "the 'trading_symbol' attribute."
            )

        return trading_symbol

    def get_positions(
            self,
            symbol: str = None,
            lazy=False
    ):

        if symbol is None:
            query_set = Position.query \
                .filter_by(portfolio=self.get_portfolio())
        else:
            query_set = Position.query \
                .filter_by(portfolio=self.get_portfolio()) \
                .filter_by(symbol=symbol)

        if lazy:
            return query_set
        else:
            return query_set.all()

    def get_orders(self, symbol: str = None, lazy=False):

        positions = Position.query \
            .filter_by(portfolio=self.get_portfolio()) \
            .with_entities(Position.id)

        if symbol is None:

            query_set = Order.query \
                .filter(Order.position_id.in_(positions))
        else:
            query_set = Order.query \
                .filter(Order.position_id.in_(positions)) \
                .filter_by(symbol=symbol)

        if lazy:
            return query_set
        else:
            return query_set.all()

    def get_pending_orders(self, symbol: str = None, lazy=False):

        if symbol is not None:
            positions = Position.query \
                .filter_by(portfolio=self.get_portfolio()) \
                .filter_by(symbol=symbol) \
                .with_entities(Position.id)
        else:
            positions = Position.query \
                .filter_by(portfolio=self.get_portfolio()) \
                .with_entities(Position.id)

        query_set = Order.query \
            .filter(Order.position_id.in_(positions)) \
            .filter_by(executed=False)

        if lazy:
            return query_set
        else:
            return query_set.all()

    def create_order(
            self,
            order_type,
            symbol,
            amount=None,
            price=None,
            order_side=OrderSide.BUY.value,
            validate_pair=True,
            context=None
    ):

        if context is None:
            context = current_app.algorithm

        return self.get_portfolio().create_buy_order(
            self,
            context,
            order_type,
            symbol,
            amount,
            price,
            order_side,
            validate_pair,
        )

    def add_order(self, order):
        self.get_portfolio().add_order(order)
