from datetime import datetime, timezone

from investing_algorithm_framework.domain import Observer, Event, \
    SNAPSHOT_INTERVAL, SnapshotInterval, OrderStatus, \
    PortfolioSnapshot, Environment, ENVIRONMENT, BACKTESTING_INDEX_DATETIME
from investing_algorithm_framework.services.repository_service import \
    RepositoryService


class PortfolioSnapshotService(RepositoryService, Observer):
    """
    Service to manage portfolio snapshots. This service will create snapshots
    of the portfolio at specific intervals or based on certain events.

    This service implements the Observer interface to listen for events.
    This can be used to register this service to an observable object
    and let it create snapshots based on the events that occur in the system.
    For example, it can create a snapshot of the portfolio
    at the end of each strategy iteration or when a trade is closed.
    """

    def __init__(
        self,
        repository,
        portfolio_repository,
        order_repository,
        position_repository,
        position_snapshot_service,
        datasource_service,
        configuration_service
    ):
        self.order_repository = order_repository
        self.position_snapshot_service = position_snapshot_service
        self.portfolio_repository = portfolio_repository
        self.position_repository = position_repository
        self.configuration_service = configuration_service
        self.datasource_service = datasource_service
        super(PortfolioSnapshotService, self).__init__(repository)

    def notify(self, event_type: Event, payload):
        """
        Update the portfolio snapshot based on the event type and payload.

        Args:
            event_type: The type of event that occurred.
            payload: The data associated with the event.
        """
        config = self.configuration_service.get_config()
        snapshot_interval = config[SNAPSHOT_INTERVAL]

        if Event.STRATEGY_RUN.equals(event_type) and \
                SnapshotInterval.STRATEGY_ITERATION.equals(snapshot_interval):
            created_at = payload.get("created_at")
            for portfolio in self.portfolio_repository.get_all():
                self.create_snapshot(portfolio, created_at=created_at)

        elif Event.TRADE_CLOSED.equals(event_type) and \
                SnapshotInterval.TRADE_CLOSE.equals(snapshot_interval):
            portfolio_id = payload.get("portfolio_id")
            created_at = payload.get("created_at")
            portfolio = self.portfolio_repository.get(portfolio_id)
            self.create_snapshot(portfolio=portfolio, created_at=created_at)

        elif Event.PORTFOLIO_CREATED.equals(event_type):
            portfolio_id = payload.get("portfolio_id")
            created_at = payload.get("created_at")
            portfolio = self.portfolio_repository.get(portfolio_id)
            self.create_snapshot(portfolio=portfolio, created_at=created_at)

        # elif Event.ORDER_CREATED.equals(event_type):
        #     portfolio_id = payload.get("portfolio_id")
        #     portfolio = self.portfolio_repository.get(portfolio_id)
        #     created_at = payload.get("created_at")
        #     self.create_snapshot(portfolio=portfolio, created_at=created_at)

    def create_snapshot(
        self, portfolio, created_at=None, cash_flow=0
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

        Returns:

        """
        pending_value = 0
        pending_orders = self.order_repository.get_all(
            {
                "status": OrderStatus.OPEN.value,
                "portfolio_id": portfolio.id
            }
        )
        created_orders = self.order_repository.get_all(
            {
                "status": OrderStatus.CREATED.value,
                "portfolio_id": portfolio.id
            }
        )

        if created_orders is not None:
            for order in created_orders:
                pending_value += order.get_price() * order.get_amount()

        if pending_orders is not None:
            for order in pending_orders:
                pending_value += order.get_price() * order.get_remaining()

        if created_at is None:
            config = self.configuration_service.get_config()

            if Environment.BACKTEST.equals(config[ENVIRONMENT]):
                created_at = config[BACKTESTING_INDEX_DATETIME]
            else:
                created_at = datetime.now(tz=timezone.utc)

        total_value = portfolio.get_unallocated() + pending_value

        for position in \
                self.position_repository.get_all({"portfolio": portfolio.id}):
            symbol = \
                f"{position.get_symbol()}/{portfolio.get_trading_symbol()}"

            if position.get_symbol() != portfolio.get_trading_symbol():
                ticker = self.datasource_service.get_ticker(symbol)

                # Calculate the position worth
                position_worth = position.get_amount() * ticker["bid"]
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
