from sqlalchemy import cast, Numeric, Float

from investing_algorithm_framework.infrastructure.models import SQLPosition
from .repository import Repository


class SQLPositionRepository(Repository):
    base_class = SQLPosition
    DEFAULT_NOT_FOUND_MESSAGE = "Position not found"

    def _apply_query_params(self, db, query, query_params):
        id_query_param = self.get_query_param("id", query_params)
        amount_query_param = self.get_query_param("amount", query_params)
        symbol_query_param = self.get_query_param("symbol", query_params)
        portfolio_query_param = self.get_query_param("portfolio", query_params)
        amount_gt_query_param = self.get_query_param("amount_gt", query_params)
        amount_gte_query_param = self.get_query_param(
            "amount_gte", query_params
        )
        amount_lt_query_param = self.get_query_param("amount_lt", query_params)
        amount_lte_query_param = self.get_query_param(
            "amount_lte", query_params
        )
        order_id_query_param = self.get_query_param("order_id", query_params)

        if id_query_param:
            query = query.filter_by(id=id_query_param)

        if amount_query_param:
            query = query.filter(
                cast(SQLPosition.amount, Float) == amount_query_param
            )

        if symbol_query_param:
            query = query.filter_by(symbol=symbol_query_param)

        if portfolio_query_param is not None:
            query = query.filter_by(portfolio_id=portfolio_query_param)

        if amount_gt_query_param is not None:
            query = query.filter(
                cast(SQLPosition.amount, Numeric) > amount_gt_query_param
            )

        if amount_gte_query_param is not None:
            query = query.filter(
                cast(SQLPosition.amount, Numeric) >= amount_gte_query_param
            )

        if amount_lt_query_param is not None:
            query = query.filter(
                cast(SQLPosition.amount, Numeric) < amount_lt_query_param
            )

        if amount_lte_query_param:
            query = query.filter(
                cast(SQLPosition.amount, Numeric) <= amount_lte_query_param
            )
        # Filter by order_id, orders is a one-to-many relationship
        # with 3 position
        if order_id_query_param:
            query = query.filter(
                SQLPosition.orders.any(id=order_id_query_param)
            )

        return query
