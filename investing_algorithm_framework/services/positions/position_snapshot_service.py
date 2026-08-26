from investing_algorithm_framework.services.repository_service \
    import RepositoryService


class PositionSnapshotService(RepositoryService):

    def create_snapshot(self, portfolio_snapshot_id, position):
        self.create(
            {
                "portfolio_snapshot_id": portfolio_snapshot_id,
                "symbol": position.symbol,
                "amount": position.amount,
                "cost": position.cost,
                "long_amount": position.long_amount,
                "short_amount": position.short_amount,
                "long_cost": position.long_cost,
                "short_cost": position.short_cost,
            }
        )

    def get_snapshots(self, portfolio_snapshot_id):
        pass
