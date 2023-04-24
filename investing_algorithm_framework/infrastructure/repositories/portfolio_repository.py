from investing_algorithm_framework.infrastructure.models import SQLPortfolio
from .repository import Repository


class SQLPortfolioRepository(Repository):
    base_class = SQLPortfolio
    DEFAULT_NOT_FOUND_MESSAGE = "Portfolio not found"

    def _apply_query_params(self, db, query, query_params):
        market_query_param = query_params.get("market")
        identifier_query_param = query_params.get("identifier")

        if market_query_param:
            query = query.filter_by(market=market_query_param.lower())

        if identifier_query_param:
            query = query.filter_by(identifier=identifier_query_param.lower())

        return query
