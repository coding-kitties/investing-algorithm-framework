from typing import List

from investing_algorithm_framework.core.identifier import Identifier
from investing_algorithm_framework.core.models import db, SQLLitePortfolio, \
    OrderType, OrderSide, Portfolio, SQLLiteOrder, OrderStatus, \
    SQLLitePosition, Position
from investing_algorithm_framework.core.order_validators import \
    OrderValidatorFactory
from investing_algorithm_framework.core.portfolio_managers.portfolio_manager \
    import PortfolioManager


class SQLLitePortfolioManager(PortfolioManager, Identifier):

    def create_portfolio(self, algorithm_context):

        portfolio = SQLLitePortfolio.query\
            .filter_by(identifier=self.get_identifier())\
            .first()

        if portfolio is None:
            portfolio = SQLLitePortfolio(
                identifier=self.get_identifier(algorithm_context),
                trading_symbol=self.get_trading_symbol(algorithm_context),
                positions=[],
                orders=[]
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
            positions = self.get_positions(algorithm_context)
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

    def get_portfolio(
        self,
        algorithm_context,
        update=False,
        execute_update=True,
        **kwargs
    ) -> Portfolio:

        portfolio = SQLLitePortfolio.query \
            .filter_by(identifier=self.identifier) \
            .first()

        return portfolio

    def create_order(
        self,
        target_symbol,
        price=None,
        type=OrderType.LIMIT,
        side=OrderSide.BUY,
        status=OrderStatus.TO_BE_SENT,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        algorithm_context=None,
        validate_pair=True
    ):
        if algorithm_context is None:
            from investing_algorithm_framework import current_app
            algorithm_context = current_app.algorithm

        order = SQLLiteOrder(
            reference_id=None,
            type=type,
            status=status,
            side=side,
            target_symbol=target_symbol,
            trading_symbol=self.get_trading_symbol(algorithm_context),
            price=price,
            amount_trading_symbol=amount_trading_symbol,
            amount_target_symbol=amount_target_symbol,
        )

        # Validate the order
        order_validator = OrderValidatorFactory.of(self.identifier)
        order_validator.validate(
            order, self.get_portfolio(algorithm_context=algorithm_context)
        )
        return order

    def add_order(self, order, algorithm_context):
        self.get_portfolio(algorithm_context).add_order(order)
        db.session.commit()
