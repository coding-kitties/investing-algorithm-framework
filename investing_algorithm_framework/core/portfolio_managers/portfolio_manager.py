from abc import abstractmethod, ABC

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Position, Order, \
    Portfolio, db, OrderType
from investing_algorithm_framework.core.identifier import Identifier


class PortfolioManager(ABC, Identifier):
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
                trading_currency=self.trading_currency,
                unallocated=self.get_initial_unallocated_size()
            )
            portfolio.save(db)

    def get_portfolio(self) -> Portfolio:
        return Portfolio.query.filter_by(
            identifier=self.identifier,
            trading_currency=self.trading_currency
        ).first()

    @property
    def unallocated(self):
        return self.get_portfolio().unallocated

    def get_trading_currency(self) -> str:

        trading_currency = getattr(self, "trading_currency", None)

        if trading_currency is None:
            raise OperationalException(
                "Trading currency is not set. Either override "
                "'get_trading_currency' method or set "
                "the 'trading_currency' attribute."
            )

        return trading_currency

    def get_positions(
            self,
            symbol: str = None,
            lazy=False
    ):

        if symbol is None:
            query_set = Position.query\
                .filter_by(portfolio=self.get_portfolio())
        else:
            query_set = Position.query\
                .filter_by(portfolio=self.get_portfolio())\
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

            query_set = Order.query\
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
                .filter_by(symbol=symbol)\
                .with_entities(Position.id)
        else:
            positions = Position.query \
                .filter_by(portfolio=self.get_portfolio()) \
                .with_entities(Position.id)

        query_set = Order.query \
            .filter(Order.position_id.in_(positions)) \
            .filter_by(executed=False)\

        if lazy:
            return query_set
        else:
            return query_set.all()

    def create_buy_order(
            self,
            symbol,
            amount,
            price=0,
            order_type=OrderType.LIMIT.value
    ):
        return self.get_portfolio().create_buy_order(
            symbol, amount, price, order_type
        )

    def create_sell_order(
            self,
            symbol,
            amount,
            price=0,
            order_type=OrderType.LIMIT.value
    ):
        return self.get_portfolio().create_sell_order(
            symbol, amount, price, order_type
        )

    def add_order(self, order):
        self.get_portfolio().add_order(order)
