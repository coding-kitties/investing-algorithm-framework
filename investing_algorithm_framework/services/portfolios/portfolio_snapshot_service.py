from investing_algorithm_framework.domain import OrderStatus, \
    PortfolioSnapshot
from investing_algorithm_framework.services.repository_service import \
    RepositoryService


class PortfolioSnapshotService(RepositoryService):
    """
    Service to manage portfolio snapshots. This service will create snapshots
    of the portfolio at specific intervals or based on certain events.
    """

    def __init__(
        self,
        repository,
        portfolio_repository,
        order_repository,
        position_repository,
        position_snapshot_service,
        data_provider_service,
    ):
        self.order_repository = order_repository
        self.position_snapshot_service = position_snapshot_service
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.data_provider_service = data_provider_service
        super(PortfolioSnapshotService, self).__init__(repository)

    def create_snapshot(
        self,
        portfolio,
        created_at,
        cash_flow=0,
        created_orders=None,
        open_orders=None,
        positions=None,
        save=True
    ) -> PortfolioSnapshot:
        """
        Function to create a snapshot of the portfolio. During
        creation, it will calculate the pending value of the
        portfolio based on the pending orders and created orders. Also,
        it will calculate the total value of the portfolio based on the
        current positions and the unallocated cash. It will do this by
        fetching the current ticker prices for each position in the portfolio.
        This function will also create position snapshots for each position
        in the portfolio and associate them with the snapshot.

        Args:
            portfolio (Portfolio): The portfolio to create a snapshot for.
            created_at (datetime, optional): The date and time when the
                snapshot was created. If not provided, the current date
                and time will be used.
            cash_flow (float, optional): The cash flow to include
                in the snapshot.
            created_orders (list, optional): A list of created orders
                to consider when calculating the pending value.
            open_orders (list, optional): A list of open orders
                to consider when calculating the pending value.
            positions (list, optional): A list of positions to consider
                when calculating the total value of the portfolio.
            save (bool, optional): Whether to save the snapshot to
                the database.

        Returns:
            PortfolioSnapshot: The created snapshot of the portfolio.
        """
        pending_value = 0
        pending_symbols = set()
        allocated = 0

        if open_orders is None:
            open_orders = self.order_repository.get_all(
                {
                    "status": OrderStatus.OPEN.value,
                    "portfolio_id": portfolio.id
                }
            )

        if created_orders is None:
            created_orders = self.order_repository.get_all(
                {
                    "status": OrderStatus.CREATED.value,
                    "portfolio_id": portfolio.id
                }
            )

        if positions is None:
            positions = self.position_repository.get_all(
                {"portfolio": portfolio.id}
            )

        for order in created_orders:
            pending_value += order.get_price() * order.get_amount()
            pending_symbols.add(order.get_symbol())

        for order in open_orders:
            pending_value += order.get_price() * order.get_remaining()
            pending_symbols.add(order.get_symbol())

        total_value = portfolio.get_unallocated() + pending_value

        for position in \
                self.position_repository.get_all({"portfolio": portfolio.id}):

            if position.get_symbol() != portfolio.get_trading_symbol():
                symbol_pair = f"{position.get_symbol()}/" \
                    f"{portfolio.get_trading_symbol()}"
                ticker = self.data_provider_service.get_ticker_data(
                    symbol=symbol_pair,
                    market=portfolio.market,
                    date=created_at
                )
                # Calculate the position worth
                position_worth = position.get_amount() * ticker["bid"]
                allocated += position_worth
                total_value += position_worth

        data = {
            "portfolio_id": portfolio.id,
            "trading_symbol": portfolio.trading_symbol,
            "pending_value": pending_value,
            "unallocated": portfolio.unallocated,
            "net_size": portfolio.net_size,
            "total_net_gain": portfolio.total_net_gain,
            "total_revenue": portfolio.total_revenue,
            "total_cost": portfolio.total_cost,
            "cash_flow": cash_flow,
            "created_at": created_at,
            "total_value": total_value,
        }
        snapshot = self.create(data, save=save)
        return snapshot

    def get_latest_snapshot(self, portfolio_id):
        pass
