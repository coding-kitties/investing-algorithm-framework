from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import BacktestDateRange, \
    BacktestRun, Portfolio, TimeFrame, PortfolioConfiguration, \
    PortfolioSnapshot, OperationalException, Order, OrderType, OrderStatus, \
    OrderSide, Trade, TradeStatus, DataType
from investing_algorithm_framework.services import DataProviderService, \
    create_backtest_metrics


# if (
#         portfolio_configurations is None
#         or len(portfolio_configurations) == 0
# ) and (
#         initial_amount is None
#         or trading_symbol is None
#         or market is None
# ):
#     raise OperationalException(
#         "No initial amount, trading symbol or market provided "
#         "for the backtest and no portfolio configurations found. "
#         "please register a portfolio configuration "
#         "or specify the initial amount, trading symbol and "
#         "market parameters before running a backtest."
#     )
#
# if portfolio_configurations is None \
#         or len(portfolio_configurations) == 0:
#     portfolio_configurations = []
#     portfolio_configurations.append(
#         PortfolioConfiguration(
#             identifier="vector_backtest",
#             market=market,
#             trading_symbol=trading_symbol,
#             initial_balance=initial_amount
#         )
#     )
#
# portfolio_configuration = portfolio_configurations[0]

class VectorBacktestService:

    def __init__(
        self, data_provider_service: DataProviderService
    ):
        self.data_provider_service = data_provider_service

    def run(
        self,
        strategy,
        backtest_date_range: BacktestDateRange,
        portfolio_configuration: PortfolioConfiguration,
        risk_free_rate: float = 0.027,
    ) -> BacktestRun:
        """
        Vectorized backtest for multiple assets using strategy
        buy/sell signals.

        Args:
            strategy: The strategy to backtest.
            backtest_date_range: The date range for the backtest.
            risk_free_rate: The risk-free rate to use for the backtest
                metrics. Default is 0.027 (2.7%).
            initial_amount: The initial amount to use for the backtest.
                If None, the initial amount will be taken from the first
                portfolio configuration.

        Returns:
            BacktestRun: The backtest run containing the results and metrics.
        """
        initial_amount = portfolio_configuration.initial_balance
        trading_symbol = portfolio_configuration.trading_symbol
        portfolio = Portfolio.from_portfolio_configuration(
            portfolio_configuration
        )

        # Load vectorized backtest data
        data = self.data_provider_service.get_vectorized_backtest_data(
            data_sources=strategy.data_sources,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date
        )

        # Compute signals from strategy
        buy_signals = strategy.generate_buy_signals(data)
        sell_signals = strategy.generate_sell_signals(data)

        # Build master index (union of all indices in signal dict)
        index = pd.Index([])

        most_granular_ohlcv_data_source = \
            self.get_most_granular_ohlcv_data_source(
                strategy.data_sources
            )

        most_granular_ohlcv_data = self.data_provider_service.get_ohlcv_data(
                symbol=most_granular_ohlcv_data_source.symbol,
                start_date=backtest_date_range.start_date,
                end_date=backtest_date_range.end_date,
                pandas=True
            )

        # Make sure to filter out the buy and sell signals that are before
        # the backtest start date
        buy_signals = {k: v[v.index >= backtest_date_range.start_date]
                       for k, v in buy_signals.items()}
        sell_signals = {k: v[v.index >= backtest_date_range.start_date]
                        for k, v in sell_signals.items()}

        index = index.union(most_granular_ohlcv_data.index)
        index = index.sort_values()

        # Initialize trades and portfolio values
        trades = []
        orders = []
        granular_ohlcv_data_order_by_symbol = {}
        snapshots = [
            PortfolioSnapshot(
                trading_symbol=trading_symbol,
                portfolio_id=portfolio.identifier,
                created_at=backtest_date_range.start_date,
                unallocated=portfolio_configuration.initial_balance,
                total_value=portfolio_configuration.initial_balance,
                total_net_gain=0.0
            )
        ]

        for symbol in buy_signals.keys():
            full_symbol = f"{symbol}/{trading_symbol}"
            # find PositionSize object
            pos_size_obj = next(
                (p for p in strategy.position_sizes if
                 p.symbol == symbol), None
            )
            # Load most granular OHLCV data for the symbol
            df = self.data_provider_service.get_ohlcv_data(
                symbol=full_symbol,
                start_date=backtest_date_range.start_date,
                end_date=backtest_date_range.end_date,
                pandas=True
            )
            granular_ohlcv_data_order_by_symbol[full_symbol] = df

            # Align signals with most granular OHLCV data
            close = df["Close"]
            buy_signal = buy_signals[symbol].reindex(index, fill_value=False)
            sell_signal = sell_signals[symbol].reindex(index, fill_value=False)

            signal = pd.Series(0, index=index)
            signal[buy_signal] = 1
            signal[sell_signal] = -1
            signal = signal.replace(0, np.nan).ffill().shift(1).fillna(0)
            signal = signal.astype(float)

            if pos_size_obj is None:
                raise OperationalException(
                    f"No position size object defined "
                    f"for symbol {symbol}, please make sure to "
                    f"register a PositionSize object in the strategy."
                )

            capital_for_trade = pos_size_obj.get_size(
                Portfolio(
                    unallocated=portfolio_configuration.initial_balance,
                    initial_balance=portfolio_configuration.initial_balance,
                    trading_symbol=trading_symbol,
                    net_size=0,
                    market="BACKTEST",
                    identifier="vector_backtest"
                ) if pos_size_obj else (initial_amount / len(buy_signals)),
                asset_price=close.iloc[0]
            )

            # Trade generation
            last_trade = None

            # Align signals with most granular OHLCV data
            close = df["Close"].reindex(index, method='ffill')
            buy_signal = buy_signals[symbol].reindex(index, fill_value=False)
            sell_signal = sell_signals[symbol].reindex(index, fill_value=False)

            # Loop over all timestamps in the backtest
            for i in range(len(index)):

                # 1 = buy, -1 = sell, 0 = hold
                current_signal = signal.iloc[i]
                current_price = float(close.iloc[i])
                current_date = index[i]

                # Convert the pd.Timestamp to an utc datetime object
                if isinstance(current_date, pd.Timestamp):
                    current_date = current_date.to_pydatetime()

                if current_date.tzinfo is None:
                    current_date = current_date.replace(tzinfo=timezone.utc)

                # If we are not in a position, and we get a buy signal
                if current_signal == 1 and last_trade is None:
                    amount = float(capital_for_trade / current_price)
                    buy_order = Order(
                        id=uuid4(),
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        order_type=OrderType.LIMIT,
                        price=current_price,
                        amount=amount,
                        status=OrderStatus.CLOSED,
                        created_at=current_date,
                        updated_at=current_date,
                        order_side=OrderSide.BUY
                    )
                    orders.append(buy_order)
                    trade = Trade(
                        id=uuid4(),
                        orders=[buy_order],
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        available_amount=amount,
                        remaining=0,
                        filled_amount=amount,
                        open_price=current_price,
                        opened_at=current_date,
                        closed_at=None,
                        amount=amount,
                        status=TradeStatus.OPEN.value,
                        cost=capital_for_trade
                    )
                    last_trade = trade
                    trades.append(trade)

                # If we are in a position, and we get a sell signal
                if current_signal == -1 and last_trade is not None:
                    net_gain_val = (
                        current_price - last_trade.open_price
                    ) * last_trade.available_amount
                    sell_order = Order(
                        id=uuid4(),
                        target_symbol=symbol,
                        trading_symbol=trading_symbol,
                        order_type=OrderType.LIMIT,
                        price=current_price,
                        amount=last_trade.available_amount,
                        status=OrderStatus.CLOSED,
                        created_at=current_date,
                        updated_at=current_date,
                        order_side=OrderSide.SELL
                    )
                    orders.append(sell_order)
                    trade_orders = last_trade.orders
                    trade_orders.append(sell_order)
                    last_trade.update(
                        {
                            "orders": trade_orders,
                            "closed_at": current_date,
                            "status": TradeStatus.CLOSED,
                            "updated_at": current_date,
                            "net_gain": net_gain_val
                        }
                    )
                    last_trade = None

        unallocated = initial_amount
        total_net_gain = 0.0
        open_trades = []

        # Create portfolio snapshots
        for ts in index:
            allocated = 0
            interval_datetime = pd.Timestamp(ts).to_pydatetime()
            interval_datetime = interval_datetime.replace(tzinfo=timezone.utc)

            for trade in trades:

                if trade.opened_at == interval_datetime:
                    # Snapshot taken at the moment a trade is opened
                    unallocated -= trade.cost
                    open_trades.append(trade)

                if trade.closed_at == interval_datetime:
                    # Snapshot taken at the moment a trade is closed
                    unallocated += trade.cost + trade.net_gain
                    total_net_gain += trade.net_gain
                    open_trades.remove(trade)

            for open_trade in open_trades:
                ohlcv = granular_ohlcv_data_order_by_symbol[
                    f"{open_trade.target_symbol}/{trading_symbol}"
                ]
                try:
                    price = ohlcv.loc[:ts, "Close"].iloc[-1]
                    open_trade.last_reported_price = price
                except IndexError:
                    continue  # skip if no price yet

                allocated += open_trade.filled_amount * price

            # total_value = invested_value + unallocated
            # total_net_gain = total_value - initial_amount
            snapshots.append(
                PortfolioSnapshot(
                    portfolio_id=portfolio.identifier,
                    created_at=interval_datetime,
                    unallocated=unallocated,
                    total_value=unallocated + allocated,
                    total_net_gain=total_net_gain
                )
            )

        unique_symbols = set()
        for trade in trades:
            unique_symbols.add(trade.target_symbol)

        number_of_trades_closed = len(
            [t for t in trades if TradeStatus.CLOSED.equals(t.status)]
        )
        number_of_trades_open = len(
            [t for t in trades if TradeStatus.OPEN.equals(t.status)]
        )
        # Create a backtest run object
        run = BacktestRun(
            trading_symbol=trading_symbol,
            initial_unallocated=initial_amount,
            number_of_runs=1,
            portfolio_snapshots=snapshots,
            trades=trades,
            orders=orders,
            positions=[],
            created_at=datetime.now(timezone.utc),
            backtest_start_date=backtest_date_range.start_date,
            backtest_end_date=backtest_date_range.end_date,
            backtest_date_range_name=backtest_date_range.name,
            number_of_days=(
                backtest_date_range.end_date - backtest_date_range.end_date
            ).days,
            number_of_trades=len(trades),
            number_of_orders=len(orders),
            number_of_trades_closed=number_of_trades_closed,
            number_of_trades_open=number_of_trades_open,
            number_of_positions=len(unique_symbols),
            symbols=list(buy_signals.keys())
        )

        # Create backtest metrics
        run.backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        return run

    @staticmethod
    def get_most_granular_ohlcv_data_source(data_sources):
        """
        Get the most granular data source from a list of data sources.

        Args:
            data_sources: List of data sources.

        Returns:
            The most granular data source.
        """
        granularity_order = {
            TimeFrame.ONE_MINUTE: 1,
            TimeFrame.FIVE_MINUTE: 5,
            TimeFrame.FIFTEEN_MINUTE: 15,
            TimeFrame.ONE_HOUR: 60,
            TimeFrame.TWO_HOUR: 120,
            TimeFrame.FOUR_HOUR: 240,
            TimeFrame.TWELVE_HOUR: 720,
            TimeFrame.ONE_DAY: 1440,
            TimeFrame.ONE_WEEK: 10080,
            TimeFrame.ONE_MONTH: 43200
        }

        most_granular = None
        highest_granularity = float('inf')

        ohlcv_data_sources = [
            ds for ds in data_sources if DataType.OHLCV.equals(ds.data_type)
        ]

        if len(ohlcv_data_sources) == 0:
            raise OperationalException("No OHLCV data sources found")

        for source in ohlcv_data_sources:

            if granularity_order[source.time_frame] < highest_granularity:
                highest_granularity = granularity_order[source.time_frame]
                most_granular = source

        return most_granular
