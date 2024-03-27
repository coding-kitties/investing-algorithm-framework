class AbstractPortfolioSyncService:
    """
    Service to sync the portfolio with the exchange.
    """
    def sync_unallocated(self, portfolio):
        pass

    def sync_positions(self, portfolio):
        pass

    def sync_orders(self, portfolio):
        pass

    def sync_trades(self, portfolio):
        pass
