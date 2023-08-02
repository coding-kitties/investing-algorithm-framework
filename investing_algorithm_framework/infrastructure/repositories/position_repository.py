from .repository import Repository
from investing_algorithm_framework.infrastructure.models import SQLPosition, \
    SQLPortfolio


class SQLPositionRepository(Repository):
    base_class = SQLPosition
    DEFAULT_NOT_FOUND_MESSAGE = "Position not found"

    def _apply_query_params(self, db, query, query_params):
        amount_query_param = self.get_query_param("amount", query_params)
        symbol_query_param = self.get_query_param("symbol", query_params)
        portfolio_query_param = self.get_query_param("portfolio", query_params)

        if amount_query_param:
            query = query.filter(SQLPosition.amount == amount_query_param)

        if symbol_query_param:
            query = query.filter_by(symbol=symbol_query_param)

        if portfolio_query_param:
            query = query.filter_by(portfolio_id=portfolio_query_param)
        return query
