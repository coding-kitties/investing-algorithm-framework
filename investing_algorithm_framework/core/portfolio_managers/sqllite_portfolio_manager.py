from typing import List
from abc import abstractmethod

from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.market_identifier import \
    MarketIdentifier
from investing_algorithm_framework.core.models import db, SQLLitePortfolio, \
    OrderType, OrderSide, Portfolio, SQLLiteOrder, \
    SQLLitePosition, Position
from investing_algorithm_framework.core.portfolio_managers.portfolio_manager \
    import PortfolioManager
from investing_algorithm_framework.core.exceptions import OperationalException


class SQLLitePortfolioManager(PortfolioManager, Identifier, MarketIdentifier):
    trading_symbol = None

    @abstractmethod
    def get_positions_from_broker(self, algorithm_context) -> List[Position]:
        pass

    def initialize(self, algorithm_context):
        self._initialize_portfolio(algorithm_context)

    def _initialize_portfolio(self, algorithm_context):
        portfolio = self.get_portfolio(algorithm_context)

        self.trading_symbol = self.get_trading_symbol(algorithm_context)

        if portfolio is None:
            positions = self.get_positions_from_broker(algorithm_context)

            if positions is None:
                raise OperationalException(
                    "Could not retrieve positions from broker"
                )

            unallocated_position = next(
                (x for x in positions if x.get_symbol()
                 == self.get_trading_symbol(algorithm_context)), None
            )

            portfolio = SQLLitePortfolio(
                identifier=self.identifier,
                trading_symbol=self.trading_symbol,
                unallocated_position=unallocated_position,
                market=self.get_market()
            )
            portfolio.save(db)

    def get_unallocated(
        self, algorithm_context, sync=False, **kwargs
    ) -> Position:
        return self.get_portfolio(algorithm_context).get_unallocated()

    def get_allocated(
        self, algorithm_context, sync=False, **kwargs
    ) -> List[Position]:
        portfolio = self.get_portfolio(algorithm_context)

        if sync:
            positions = self.get_positions_from_broker(algorithm_context)
            old_positions = portfolio.get_positions()

            for position in positions:
                old_position = next((x for x in old_positions if x.get_symbol()
                                     == position.get_symbol()), None)

                if old_position is not None:
                    old_position.amount = position.amount
                    db.session.commit()
                else:
                    position = SQLLitePosition.from_position(position)
                    portfolio.positions.append(position)
                    db.session.commit()

        return portfolio.get_allocated()

    def get_portfolio(self, algorithm_context, **kwargs) -> Portfolio:
        portfolio = SQLLitePortfolio.query\
            .filter_by(identifier=self.identifier)\
            .first()

        return portfolio

    def get_positions(
        self, algorithm_context, sync=False, lazy=False, **kwargs
    ):
        query_set = SQLLitePosition.query \
            .filter_by(portfolio=self.get_portfolio(algorithm_context)) \

        if lazy:
            return query_set
        else:
            return query_set.all()

    def get_orders(self, algorithm_context, sync=False, lazy=False, **kwargs):
        positions = SQLLitePosition.query \
            .filter_by(portfolio=self.get_portfolio(algorithm_context)) \
            .with_entities(SQLLitePosition.id)

        query_set = SQLLiteOrder.query \
            .filter(SQLLiteOrder.position_id.in_(positions))

        if lazy:
            return query_set
        else:
            return query_set.all()

    def create_order(
        self,
        target_symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_type=OrderType.LIMIT.value,
        order_side=OrderSide.BUY.value,
        algorithm_context=None,
        validate_pair=True
    ):

        if algorithm_context is None:
            from investing_algorithm_framework import current_app
            algorithm_context = current_app.algorithm

        return self.get_portfolio(algorithm_context).create_order(
            algorithm_context=algorithm_context,
            order_type=order_type,
            target_symbol=target_symbol,
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
            order_side=order_side,
        )

    def add_order(self, order, algorithm_context):
        self.get_portfolio(algorithm_context).orders.append(order)
        db.session.commit()
