from investing_algorithm_framework.infrastructure.models import SQLOrderFee
from .repository import Repository


class SQLOrderFeeRepository(Repository):
    base_class = SQLOrderFee
    DEFAULT_NOT_FOUND_MESSAGE = "Order fee not found"

    def _apply_query_params(self, db, query, query_params):
        order_query_param = self.get_query_param("order", query_params)

        if order_query_param:
            query = query.filter_by(order_id=order_query_param)

        return query
