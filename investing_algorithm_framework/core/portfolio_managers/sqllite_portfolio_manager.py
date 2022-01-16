from abc import abstractmethod

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.market_identifier import \
    MarketIdentifier
from investing_algorithm_framework.core.models import db, Portfolio, \
    Position, Order, OrderStatus, OrderType, OrderSide
from investing_algorithm_framework.core.portfolio_managers.portfolio_manager\
    import PortfolioManager


class SQLLitePortfolioManager(PortfolioManager, Identifier, MarketIdentifier):
    trading_symbol = None

    @abstractmethod
    def get_unallocated_synced(self, algorithm_context):
        pass

    @abstractmethod
    def get_positions_synced(self, algorithm_context):
        pass

    def initialize(self, algorithm_context):
        self._initialize_portfolio(algorithm_context)

    def _initialize_portfolio(self, algorithm_context):
        portfolio = self.get_portfolio(False)

        self.trading_symbol = self.get_trading_symbol(algorithm_context)

        if portfolio is None:
            portfolio = Portfolio(
                identifier=self.identifier,
                trading_symbol=self.trading_symbol,
                unallocated=self.get_unallocated_synced(algorithm_context),
                market=self.get_market()
            )
            portfolio.save(db)

    def get_unallocated(self, algorithm_context, sync=False):
        portfolio = self.get_portfolio()

        if sync:
            unallocated = self.get_unallocated_synced(algorithm_context)

            if portfolio.unallocated != unallocated:
                portfolio.unallocated = unallocated
                db.session.commit()

        return portfolio.unallocated

    def get_allocated(self, algorithm_context, sync=False):
        portfolio = self.get_portfolio()

        if sync:
            synced_positions = self.get_positions_synced(algorithm_context)
            positions = Position.query.filter_by(portfolio=self.get_portfolio())

            for synced_position in synced_positions:

                position = positions\
                    .filter_by(symbol=synced_position["symbol"])\
                    .first()

                if position is None:

                    position = Position(symbol=synced_position["symbol"])
                    position.amount = synced_position["amount"]
                    position.portfolio = portfolio
                    db.session.commit()
                elif position.amount != synced_position["amount"]:
                    position.amount = synced_position["amount"]
                    db.session.commit()

        return portfolio.unallocated

    def get_portfolio(self, throw_exception=True) -> Portfolio:
        portfolio = Portfolio.query\
            .filter_by(identifier=self.identifier)\
            .first()

        if portfolio is None and throw_exception:
            raise OperationalException("No portfolio model implemented")

        return portfolio

    def get_positions(self, symbol: str = None, lazy=False):

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

    def get_orders(self, symbol: str = None, status=None, lazy=False):
        positions = Position.query \
            .filter_by(portfolio=self.get_portfolio()) \
            .with_entities(Position.id)

        query_set = Order.query \
            .filter(Order.position_id.in_(positions))

        if symbol is not None:
            query_set = query_set.filter_by(symbol=symbol)

        if status is not None:
            status = OrderStatus.from_value(status)
            query_set = query_set.filter_by(status=status.value)

        if lazy:
            return query_set
        else:
            return query_set.all()

    def create_order(
        self,
        symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_type=OrderType.LIMIT.value,
        order_side=OrderSide.BUY.value,
        context=None,
        validate_pair=True,
    ):

        if context is None:
            from investing_algorithm_framework import current_app
            context = current_app.algorithm

        return self.get_portfolio().create_order(
            context=context,
            order_type=order_type,
            symbol=symbol,
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            order_side=order_side,
            validate_pair=validate_pair
        )

    def add_order(self, order):
        self.get_portfolio().add_order(order)
