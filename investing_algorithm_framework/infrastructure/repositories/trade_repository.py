import logging
from sqlalchemy.exc import SQLAlchemyError

from investing_algorithm_framework.domain import OrderStatus, ApiException
from investing_algorithm_framework.infrastructure.models import SQLPosition, \
    SQLPortfolio, SQLTrade, SQLOrder
from investing_algorithm_framework.infrastructure.database import Session

from .repository import Repository

logger = logging.getLogger("investing_algorithm_framework")


class SQLTradeRepository(Repository):
    base_class = SQLTrade
    DEFAULT_NOT_FOUND_MESSAGE = "The requested trade was not found"

    def _apply_query_params(self, db, query, query_params):
        portfolio_query_param = self.get_query_param(
            "portfolio_id", query_params
        )
        status_query_param = self.get_query_param("status", query_params)
        target_symbol = self.get_query_param(
            "target_symbol", query_params
        )
        trading_symbol = self.get_query_param("trading_symbol", query_params)
        order_id_query_param = self.get_query_param("order_id", query_params)

        if order_id_query_param:
            query = query.filter(SQLTrade.orders.any(id=order_id_query_param))

        if portfolio_query_param is not None:
            portfolio = db.query(SQLPortfolio).filter_by(
                id=portfolio_query_param
            ).first()

            if portfolio is None:
                raise ApiException("Portfolio not found")

            # Query trades belonging to the portfolio
            query = db.query(SQLTrade).join(SQLOrder, SQLTrade.orders) \
                .join(SQLPosition, SQLOrder.position_id == SQLPosition.id) \
                .filter(SQLPosition.portfolio_id == portfolio.id)

        if status_query_param:
            status = OrderStatus.from_value(status_query_param)
            # Explicitly filter on SQLTrade.status
            query = query.filter(SQLTrade.status == status.value)

        if target_symbol:
            # Explicitly filter on SQLTrade.target_symbol
            query = query.filter(SQLTrade.target_symbol == target_symbol)

        if trading_symbol:
            # Explicitly filter on SQLTrade.trading_symbol
            query = query.filter(SQLTrade.trading_symbol == trading_symbol)

        return query

    def add_order_to_trade(self, trade, order):
        with Session() as db:
            try:
                db.add(order)
                db.add(trade)
                trade.orders.append(order)
                db.commit()
                return trade
            except SQLAlchemyError as e:
                logger.error(f"Error saving trade: {e}")
                db.rollback()
                raise ApiException("Error saving trade")
