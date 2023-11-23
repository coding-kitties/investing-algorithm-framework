from datetime import datetime

from investing_algorithm_framework.services.repository_service import \
    RepositoryService
from investing_algorithm_framework.domain import parse_decimal_to_string


class PortfolioSnapshotService(RepositoryService):

    def __init__(
        self,
        repository,
        position_repository,
        position_snapshot_service
    ):
        self.position_snapshot_service = position_snapshot_service
        self.position_repository = position_repository
        super(PortfolioSnapshotService, self).__init__(repository)

    def create_snapshot(
        self,
        portfolio,
        pending_orders=None,
        created_orders=None,
        created_at=None,
        cash_flow=0
    ):
        pending_value = 0

        if created_orders is not None:
            for order in created_orders:
                pending_value += order.get_price() * order.get_amount()

        if pending_orders is not None:
            for order in pending_orders:
                pending_value += order.get_price() * order.get_remaining()

        if created_at is None:
            created_at = datetime.now()

        data = {
            "portfolio_id": portfolio.id,
            "trading_symbol": portfolio.trading_symbol,
            "pending_value": pending_value,
            "unallocated": portfolio.unallocated,
            "total_net_gain": portfolio.total_net_gain,
            "total_revenue": portfolio.total_revenue,
            "total_cost": portfolio.total_cost,
            "cash_flow": cash_flow,
            "created_at": created_at,
        }
        snapshot = self.create(data)
        positions = self.position_repository.get_all(
            {"portfolio": portfolio.id}
        )

        for position in positions:
            self.position_snapshot_service.create_snapshot(
                snapshot.id, position
            )

        return snapshot

    def get_latest_snapshot(self, portfolio_id):
        pass

    def get_snapshots(self, portfolio_id, start_date=None, end_date=None):
        pass
