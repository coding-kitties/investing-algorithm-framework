from investing_algorithm_framework.domain import OrderStatus
from investing_algorithm_framework.infrastructure.models import SQLPosition, \
    SQLPortfolio, SQLTrade
from .repository import Repository


class SQLTradeRepository(Repository):
    base_class = SQLTrade
    DEFAULT_NOT_FOUND_MESSAGE = "The requested trade was not found"

    def _apply_query_params(self, db, query, query_params):
        portfolio_query_param = self.get_query_param(
            "portfolio_id", query_params
        )
        status_query_param = self.get_query_param("status", query_params)
        target_symbol = self.get_query_param("target_symbol", query_params)
        trading_symbol = self.get_query_param("trading_symbol", query_params)

        if portfolio_query_param is not None:
            portfolio = db.query(SQLPortfolio).filter_by(
                id=portfolio_query_param
            ).first()

            if portfolio:
                positions = db.query(SQLPosition).filter_by(
                    portfolio_id=portfolio.id
                ).all()
                position_ids = [p.id for p in positions]
                query = query.filter(SQLTrade.position_id.in_(position_ids))
            else:
                query = query.filter_by(id=None)

        if status_query_param:
            status = OrderStatus.from_value(status_query_param)
            query = query.filter_by(status=status.value)

        if target_symbol:
            query = query.filter_by(target_symbol=target_symbol)

        if trading_symbol:
            query = query.filter_by(trading_symbol=trading_symbol)

        return query
