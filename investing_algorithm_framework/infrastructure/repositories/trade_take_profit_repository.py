import logging

from investing_algorithm_framework.infrastructure.models import \
    SQLTradeTakeProfit

from .repository import Repository

logger = logging.getLogger("investing_algorithm_framework")


class SQLTradeTakeProfitRepository(Repository):
    base_class = SQLTradeTakeProfit
    DEFAULT_NOT_FOUND_MESSAGE = "The requested trade take profit was not found"

    def _apply_query_params(self, db, query, query_params):
        trade_query_param = self.get_query_param("trade_id", query_params)

        if trade_query_param:
            query = query.filter(
                SQLTradeTakeProfit.trade_id == trade_query_param
            )

        return query
