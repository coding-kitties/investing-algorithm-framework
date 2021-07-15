from abc import abstractmethod, ABC

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Position, Order, \
    Portfolio, OrderSide, db


class AbstractPortfolioManager(ABC):
    broker = None
    base_currency = None

    def __init__(
            self,
            broker: str = None,
            base_currency: str = None,
    ):

        if self.broker is None:
            self.broker = broker

        if self.broker is None:
            raise OperationalException(
                "Portfolio manager has no broker specified"
            )

        if self.base_currency is None:
            self.base_currency = base_currency

        if self.base_currency is None:
            raise OperationalException(
                "Portfolio manager has no base currency defined"
            )

    def initialize(self):
        self._initialize_portfolio()

    def _initialize_portfolio(self):
        portfolio = self.get_portfolio()

        if portfolio is None:
            portfolio = Portfolio(
                broker=self.broker,
                base_currency=self.base_currency,
                unallocated=self.get_unallocated_size()
            )
            portfolio.save(db)

    @property
    def unallocated(self):
        return self.get_unallocated_size()

    def get_broker(self) -> str:
        assert getattr(self, 'broker', None) is not None, (
            "{} should either include a broker attribute, or override the "
            "`get_broker()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'broker')

    def get_base_currency(self) -> str:
        assert getattr(self, 'base_currency', None) is not None, (
            "{} should either include a base_currency attribute, or override "
            "the `get_base_currency()`, method.".format(
                self.__class__.__name__
            )
        )

        return getattr(self, 'broker')

    @abstractmethod
    def get_unallocated_size(self) -> float:
        raise NotImplementedError()

    @abstractmethod
    def get_positions(self, symbol: str = None):
        raise NotImplementedError()

    @abstractmethod
    def get_orders(self, symbol: str = None):
        raise NotImplementedError()

    @abstractmethod
    def add_buy_order(self, order):
        raise NotImplementedError()

    @abstractmethod
    def add_sell_order(self, order):
        raise NotImplementedError()

    @abstractmethod
    def create_buy_order(self, symbol, amount, price):
        raise NotImplementedError()

    @abstractmethod
    def create_sell_order(self, symbol, amount, price):
        raise NotImplementedError()

    def get_portfolio(self) -> Portfolio:
        return Portfolio.query.filter_by(
            broker=self.broker,
            base_currency=self.base_currency
        ).first()


class PortfolioManager(AbstractPortfolioManager, ABC):

    def __init__(
            self,
            broker: str = None,
            base_currency: str = None
    ):
        super(PortfolioManager, self).__init__(broker, base_currency)

    def get_positions(self, symbol: str = None, trading_symbol: str = None):

        if symbol is None:
            return Position.query\
                .filter_by(portfolio=self.get_portfolio()) \
                .all()
        else:
            return Position.query\
                .filter_by(broker=self.get_broker())\
                .filter_by(symbol=symbol)\
                .all()

    def get_orders(self, symbol: str = None):

        positions = Position.query \
            .filter_by(portfolio=self.get_portfolio()) \
            .with_entities(Position.id)

        if symbol is None:

            return Order.query\
                .filter(Order.position_id.in_(positions))\
                .all()
        else:
            return Order.query \
                .filter(Order.position_id.in_(positions)) \
                .filter_by(symbol=symbol)\
                .all()

    def create_buy_order(self, symbol, amount, price):
        return Order(
            trading_symbol=self.base_currency,
            target_symbol=symbol,
            amount=amount,
            price=price,
            order_side=OrderSide.BUY.value
        )

    def create_sell_order(self, symbol, amount, price):
        return Order(
            trading_symbol=symbol,
            target_symbol=self.base_currency,
            amount=amount,
            price=price,
            order_side=OrderSide.SELL.value
        )

    def add_buy_order(self, order):
        self.get_portfolio().add_buy_order(order)

    def add_sell_order(self, order):
        self.get_portfolio().add_sell_order(order)
