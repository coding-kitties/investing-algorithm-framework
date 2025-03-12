from investing_algorithm_framework.infrastructure.models import SQLPortfolio, \
    SQLPosition
from .repository import Repository


class SQLPortfolioRepository(Repository):
    base_class = SQLPortfolio
    DEFAULT_NOT_FOUND_MESSAGE = "Portfolio not found"

    def _apply_query_params(self, db, query, query_params):
        id_query_param = query_params.get("id")
        market_query_param = query_params.get("market")
        identifier_query_param = query_params.get("identifier")
        position_query_param = query_params.get("position")

        if id_query_param:
            query = query.filter_by(id=id_query_param)

        if market_query_param:
            query = query.filter_by(market=market_query_param.upper())

        if identifier_query_param:
            query = query.filter_by(identifier=identifier_query_param.upper())

        if position_query_param:
            position = db.query(SQLPosition)\
                .filter_by(id=position_query_param).first()
            query = query.filter_by(id=position.portfolio_id)

        return query
