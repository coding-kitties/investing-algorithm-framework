from investing_algorithm_framework.services import PortfolioSyncService


class PortfolioSyncServiceStub:
    """
    Stub class for PortfolioSyncService. This class is used to test the
    PortfolioSyncService class without actually executing any orders.
    """

    def __init__(self, portfolio_repository, position_repository):
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository

    def sync_unallocated(self, portfolio):
        if portfolio.initial_balance is None:
            unallocated = 1000
        else:
            unallocated = portfolio.initial_balance

        update_data = {
            "unallocated": unallocated,
            "net_size": unallocated,
            "initialized": True
        }
        portfolio = self.portfolio_repository.update(
            portfolio.id, update_data
        )

        # Update also a trading symbol position
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio_id": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id, {"amount": unallocated}
        )

        return portfolio

    def sync_orders(self, portfolio):
        return
