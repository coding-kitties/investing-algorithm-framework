from investing_algorithm_framework.services.repository_service import \
    RepositoryService


class PositionService(RepositoryService):

    def __init__(self, repository, market_service):
        super().__init__(repository)
        self.market_service = market_service

    def sync_positions(self, portfolio, market_service):
        self.market_service.initialize(portfolio.portfolio_configuration)
        balances = self.market_service.balances()

        # Get trading symbol position
        trading_symbol_position = balances[portfolio.get_trading_symbol()]

        if portfolio.portfolio_configuration.has_unallocated_limit \
                and trading_symbol_position["free"] > \
                portfolio.portfolio_configuration.max_unallocated:
            self._sync_position(
                portfolio.portfolio_configuration.max_unallocated,
                portfolio.id,
                portfolio.get_trading_symbol(),
            )
        else:
            self._sync_position(
                trading_symbol_position["free"],
                portfolio.id,
                portfolio.get_trading_symbol(),
            )

        for balance_entry in balances:
            symbol = balance_entry

            if symbol == portfolio.get_trading_symbol():
                continue

            if "free" in balances[symbol]:
                self._sync_position(
                    balances[symbol]["free"],
                    portfolio.id,
                    symbol,
                )

    def _sync_position(self, synced_amount, portfolio_id, symbol):
        position = self.find({"symbol": symbol, "portfolio": portfolio_id})

        if position.amount != synced_amount:
            self.update(position.id, {"amount": synced_amount})
