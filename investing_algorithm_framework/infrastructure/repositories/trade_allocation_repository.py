from investing_algorithm_framework.infrastructure.models import \
    SQLTradeAllocation
from .repository import Repository


class SQLTradeAllocationRepository(Repository):
    base_class = SQLTradeAllocation
    DEFAULT_NOT_FOUND_MESSAGE = \
        "The requested trade allocation was not found"

    def _apply_query_params(self, db, query, query_params):

        if "order_id" in query_params:
            query = query.filter(
               SQLTradeAllocation.order_id == query_params["order_id"]
            )

        return query
