from investing_algorithm_framework.infrastructure.models import \
    SQLPortfolioSnapshot
from .repository import Repository


class SQLPortfolioSnapshotRepository(Repository):
    base_class = SQLPortfolioSnapshot
    DEFAULT_NOT_FOUND_MESSAGE = "Portfolio snapshot not found"

    def _apply_query_params(self, db, query, query_params):
        portfolio_id_query_param = self.get_query_param(
            "portfolio_id", query_params
        )
        created_at_query_param = self.get_query_param(
            "created_at", query_params
        )
        created_at_gt_query_param = self.get_query_param(
            "created_at_gt", query_params
        )
        created_at_gte_query_param = self.get_query_param(
            "created_at_gte", query_params
        )
        created_at_lt_query_param = self.get_query_param(
            "created_at_lt", query_params
        )
        created_at_lte_query_param = self.get_query_param(
            "created_at_lte", query_params
        )

        if portfolio_id_query_param is not None:
            query = query.filter_by(portfolio_id=portfolio_id_query_param)

        if created_at_query_param is not None:
            query = query.filter_by(created_at=created_at_query_param)

        if created_at_gt_query_param is not None:
            query = query.filter(
                SQLPortfolioSnapshot.created_at > created_at_gt_query_param
            )

        if created_at_gte_query_param is not None:
            query = query.filter(
                SQLPortfolioSnapshot.created_at >= created_at_gt_query_param
            )

        if created_at_lt_query_param is not None:
            query = query.filter(
                SQLPortfolioSnapshot.created_at < created_at_lt_query_param
            )

        if created_at_lte_query_param is not None:
            query = query.filter(
                SQLPortfolioSnapshot.created_at <= created_at_lte_query_param
            )

        return query
