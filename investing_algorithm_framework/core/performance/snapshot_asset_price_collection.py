from investing_algorithm_framework.core.models import TimeFrame
from investing_algorithm_framework.core.models.snapshots \
    import AssetPriceHistory, PortfolioSnapshot
from investing_algorithm_framework.core.performance.asset_price_queue \
    import AssetPricesQueue
from investing_algorithm_framework.core.performance.snapshot_queue \
    import SnapShotQueue
from investing_algorithm_framework.core.performance.intervals_queue \
    import IntervalsQueue


class SnapshotAssetPriceCollection:
    """
    SnapshotAssetPriceCollection is a class that implements the iterator design
    pattern to match portfolio snapshots with asset prices based on
    specific time intervals.

    Iterating over this data structure, gives you a time interval, a snapshot
    and a set of asset prices
    """

    def __init__(self, portfolio, time_frame: TimeFrame):
        self.time_frame = TimeFrame.from_value(time_frame).value
        self.portfolio = portfolio

        # Retrieve snapshots
        self.snapshots = self._retrieve_snapshots(portfolio, time_frame)
        self.asset_prices = self._retrieve_asset_price_histories(
            self._retrieve_unique_symbols(), self.time_frame
        )
        self.current_snapshot = None
        self.current_date = None
        self.index = 0
        self.intervals = IntervalsQueue(self.time_frame)

    def __iter__(self):
        self.snapshot_queue = SnapShotQueue(self.snapshots)
        self.intervals = IntervalsQueue(self.time_frame)
        self.asset_prices_queue = AssetPricesQueue(
            self.asset_prices, self.time_frame
        )
        self.current_snapshot = self.snapshot_queue.pop()
        self.current_date, self.current_asset_prices = \
            self.asset_prices_queue.pop()
        self.first_snapshot = self.current_snapshot
        return self

    def __next__(self):

        if self.asset_prices_queue.empty():
            raise StopIteration

        peek_snapshot = self.snapshot_queue.peek()

        # Check if the current snapshot is the pre-first one
        if self.first_snapshot.id == self.current_snapshot.id:

            # There is no snapshot for this time interval
            if self.current_snapshot.created_at > self.current_date:
                datetime = self.current_date
                asset_prices = self.current_asset_prices
                self.current_date, self.current_asset_prices = \
                    self.asset_prices_queue.pop()
                return datetime, None, asset_prices

            if peek_snapshot is not None \
                    and peek_snapshot.created_at >= self.current_date:
                datetime = self.current_date
                asset_prices = self.current_asset_prices
                snapshot = self.current_snapshot
                self.current_date, self.current_asset_prices = \
                    self.asset_prices_queue.pop()
                self.current_snapshot = self.snapshot_queue.pop()
                return datetime, snapshot, asset_prices
            else:
                datetime = self.current_date
                asset_prices = self.current_asset_prices
                self.current_date, self.current_asset_prices = \
                    self.asset_prices_queue.pop()
                return datetime, self.current_snapshot, asset_prices

        # Check if we need to pop prices and interval time
        if peek_snapshot is not None:

            if peek_snapshot.created_at >= self.current_date:
                snapshot = self.current_snapshot
                interval = self.current_date
                asset_prices = self.current_asset_prices

                # Pop from queues
                self.current_snapshot = self.snapshot_queue.pop()
                self.current_date, self.asset_prices \
                    = self.asset_prices_queue.pop()

                return interval, snapshot, asset_prices
            else:
                snapshot = self.current_snapshot

                # Make known to the snapshot that it is an inner snapshot
                snapshot.inner_snapshot = True

                # Pop snapshot from queue
                self.current_snapshot = self.snapshot_queue.pop()
                return snapshot.created_at, snapshot, self.asset_prices
        else:
            datetime = self.current_date
            asset_prices = self.current_asset_prices
            self.current_date, self.current_asset_prices = \
                self.asset_prices_queue.pop()
            return datetime, self.current_snapshot, asset_prices

    def _retrieve_unique_symbols(self):
        unique_symbols = []

        # Get unique symbols
        for portfolio_snapshot in self.snapshots:
            for position in portfolio_snapshot.positions:
                if position.symbol not in unique_symbols:
                    unique_symbols.append(position.symbol)

        return unique_symbols

    def _retrieve_asset_price_histories(self, symbols, time_frame):
        asset_prices = []

        # Retrieve and save the price histories
        for symbol in symbols:
            asset_price_history = AssetPriceHistory.of(
                market=self.portfolio.market,
                target_symbol=symbol,
                trading_symbol=self.portfolio.trading_symbol,
                time_frame=time_frame
            )

            asset_prices.append(asset_price_history.get_prices())
        return asset_prices

    def _retrieve_snapshots(self, portfolio, time_frame):

        start_datetime, end_datetime = time_frame.create_time_frame()

        snapshots = PortfolioSnapshot.query\
            .filter(PortfolioSnapshot.created_at >= start_datetime)\
            .filter(PortfolioSnapshot.created_at <= end_datetime)\
            .order_by(PortfolioSnapshot.created_at.desc())\
            .all()

        if(PortfolioSnapshot.query
                .filter_by(portfolio_id=portfolio.id)
                .filter(PortfolioSnapshot.created_at < start_datetime)
                .count() > 0):
            additional_snapshot = PortfolioSnapshot.query \
                .filter_by(portfolio_id=portfolio.id)\
                .filter(PortfolioSnapshot.created_at < start_datetime) \
                .order_by(PortfolioSnapshot.created_at.asc())\
                .first()

            snapshots.append(additional_snapshot)

        return snapshots
