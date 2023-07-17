from investing_algorithm_framework.infrastructure.models import SQLPositionCost
from .repository import Repository


class SQLPositionCostRepository(Repository):
    base_class = SQLPositionCost
    DEFAULT_NOT_FOUND_MESSAGE = "Position cost not found"

    def _apply_query_params(self, db, query, query_params):
        position_query_param = self.get_query_param("position", query_params)

        if position_query_param:
            query = query.filter_by(position_id=position_query_param)

        query = query.order_by(SQLPositionCost.created_at.desc())
        return query
