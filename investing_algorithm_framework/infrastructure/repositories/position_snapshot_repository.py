from investing_algorithm_framework.infrastructure.models import \
    SQLPositionSnapshot
from .repository import Repository


class SQLPositionSnapshotRepository(Repository):
    base_class = SQLPositionSnapshot
    DEFAULT_NOT_FOUND_MESSAGE = "Position snapshot not found"

    def _apply_query_params(self, db, query, query_params):
        portfolio_snapshot_query_param = self.get_query_param(
            "portfolio_snapshot", query_params
        )

        if portfolio_snapshot_query_param is not None:
            query = query\
                .filter_by(
                    portfolio_snapshot_id=portfolio_snapshot_query_param
                )

        return query
