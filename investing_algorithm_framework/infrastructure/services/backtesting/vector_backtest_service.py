from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from investing_algorithm_framework.domain import BacktestDateRange, \
    BacktestRun, Portfolio, TimeFrame, PortfolioConfiguration, \
    PortfolioSnapshot, OperationalException, Order, OrderType, OrderStatus, \
    OrderSide, Trade, TradeStatus, DataType
from investing_algorithm_framework.services import DataProviderService, \
    create_backtest_metrics


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
        dynamic_position_sizing: bool = False,
    ) -> BacktestRun:
        """
        Vectorized backtest for multiple assets using strategy
        buy/sell signals.

        Args:
            strategy: The strategy to backtest.
            backtest_date_range: The date range for the backtest.
            portfolio_configuration: Portfolio configuration containing
                initial balance, market, and trading symbol.
            risk_free_rate: The risk-free rate to use for the backtest
                metrics. Default is 0.027 (2.7%).
            dynamic_position_sizing: If True, position sizes are recalculated
                at each trade based on current portfolio value (similar to
                event-based backtesting). If False (default), position sizes
                are calculated once at the start based on initial portfolio
                value. Default is False for backward compatibility.

        Returns:
            BacktestRun: The backtest run containing the results and metrics.

        Note:
            Signal generation uses a warmup window: the strategy receives
            data starting from ``start_date - window_size * timeframe``
            so that indicators (e.g. 100-day MA) are fully primed.
            However, only signals on or after ``start_date`` produce
            trades. If you need to replicate signals externally, make
            sure to include the same warmup period in your data.
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

        # Pre-compute all data needed for each symbol
        symbol_data = {}
        for symbol in buy_signals.keys():
            full_symbol = f"{symbol}/{trading_symbol}"

            # find PositionSize object
            pos_size_obj = next(
                (p for p in strategy.position_sizes if
                 p.symbol == symbol), None
            )

            if pos_size_obj is None:
                raise OperationalException(
                    f"No position size object defined "
                    f"for symbol {symbol}, please make sure to "
                    f"register a PositionSize object in the strategy."
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
            close = df["Close"].reindex(index, method='ffill')

            # Use raw boolean signals directly instead of ffill
            # state machine (which discards subsequent buy signals
            # in the same cluster). The per-bar last_trade check
            # already enforces one-position-at-a-time per symbol.
            buy_signal = buy_signals[symbol].reindex(index, fill_value=False)
            sell_signal = sell_signals[symbol].reindex(
                index, fill_value=False
            )

            # Calculate initial capital for trade
            # (used when dynamic_position_sizing=False)
            initial_capital_for_trade = pos_size_obj.get_size(
                Portfolio(
                    unallocated=portfolio_configuration.initial_balance,
                    initial_balance=portfolio_configuration.initial_balance,
                    trading_symbol=trading_symbol,
                    net_size=0,
                    market="BACKTEST",
                    identifier="vector_backtest"
                ),
                asset_price=close.iloc[0] if len(close) > 0 else 1.0
            )

            symbol_data[symbol] = {
                'full_symbol': full_symbol,
                'pos_size_obj': pos_size_obj,
                'close': close,
                'buy_signal': buy_signal,
                'sell_signal': sell_signal,
                'initial_capital_for_trade': initial_capital_for_trade,
                'last_trade': None,  # Track open trade per symbol
            }

        # Signal event log — records every fired signal and its outcome
        signal_events = []

        # Shared portfolio state for dynamic position sizing
        current_unallocated = initial_amount
        total_realized_gains = 0.0
        total_allocated = 0.0  # Track total allocated in static mode
        open_trades_value = {}  # Track value of open trades per symbol

        def _close_trade(sym, sym_data, price, date):
            """Helper to close an open trade for a symbol."""
            nonlocal current_unallocated, total_realized_gains, \
                total_allocated

            lt = sym_data['last_trade']
            net_gain_val = (
                price - lt.open_price
            ) * lt.available_amount

            # Update shared portfolio state
            if dynamic_position_sizing:
                current_unallocated += lt.cost + net_gain_val
                total_realized_gains += net_gain_val
                if sym in open_trades_value:
                    del open_trades_value[sym]
            else:
                total_allocated -= lt.cost

            sell_order = Order(
                id=uuid4(),
                target_symbol=sym,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT,
                price=price,
                amount=lt.available_amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.SELL
            )
            orders.append(sell_order)
            trade_orders = lt.orders
            trade_orders.append(sell_order)

            lt.update(
                {
                    "orders": trade_orders,
                    "closed_at": date,
                    "status": TradeStatus.CLOSED.value,
                    "updated_at": date,
                    "net_gain": net_gain_val,
                }
            )
            sym_data['last_trade'] = None

        # Process all timestamps in chronological order
        for i in range(len(index)):
            current_date = index[i]

            # Convert the pd.Timestamp to an utc datetime object
            if isinstance(current_date, pd.Timestamp):
                current_date = current_date.to_pydatetime()

            if current_date.tzinfo is None:
                current_date = current_date.replace(tzinfo=timezone.utc)

            # Process each symbol at this timestamp
            for symbol, data in symbol_data.items():
                current_price = float(data['close'].iloc[i])
                pos_size_obj = data['pos_size_obj']
                last_trade = data['last_trade']

                # Read raw boolean signals for this bar
                is_buy = bool(data['buy_signal'].iloc[i])
                is_sell = bool(data['sell_signal'].iloc[i])

                # Issue 5: Explicit handling of simultaneous buy+sell
                # — sell takes priority (closes existing position first)
                if is_buy and is_sell:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": False,
                        "reason": "sell_priority_on_conflict",
                    })
                    is_buy = False  # sell takes priority on conflicts

                # --- SELL ---
                if is_sell and last_trade is not None:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "sell",
                        "executed": True,
                        "reason": "executed",
                    })
                    _close_trade(
                        symbol, data, current_price, current_date
                    )
                    last_trade = data['last_trade']  # now None
                elif is_sell and last_trade is None:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "sell",
                        "executed": False,
                        "reason": "no_position_to_close",
                    })

                # --- BUY ---
                if is_buy and last_trade is None:
                    # Calculate capital for this trade
                    if dynamic_position_sizing:
                        # Calculate current portfolio value:
                        # unallocated + value of all open trades
                        open_trades_total = sum(open_trades_value.values())
                        current_portfolio_value = \
                            current_unallocated + open_trades_total
                        capital_for_trade = pos_size_obj.get_size(
                            Portfolio(
                                unallocated=current_portfolio_value,
                                initial_balance=initial_amount,
                                trading_symbol=trading_symbol,
                                net_size=0,
                                market="BACKTEST",
                                identifier="vector_backtest"
                            ),
                            asset_price=current_price
                        )
                        # Don't exceed available unallocated funds
                        capital_for_trade = min(
                            capital_for_trade, current_unallocated
                        )
                    else:
                        capital_for_trade = data['initial_capital_for_trade']

                        # Issue 6: Guard against exceeding total portfolio
                        # allocation even in static position sizing mode
                        if total_allocated + capital_for_trade \
                                > initial_amount:
                            signal_events.append({
                                "date": current_date,
                                "symbol": symbol,
                                "signal": "buy",
                                "executed": False,
                                "reason": "insufficient_capital",
                            })
                            continue

                    if capital_for_trade <= 0:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "buy",
                            "executed": False,
                            "reason": "insufficient_capital",
                        })
                        continue  # Skip if no capital available

                    amount = float(capital_for_trade / current_price)

                    # Update shared portfolio state
                    if dynamic_position_sizing:
                        current_unallocated -= capital_for_trade
                    else:
                        total_allocated += capital_for_trade

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
                    data['last_trade'] = trade
                    trades.append(trade)
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": True,
                        "reason": "executed",
                    })

                    # Track open trade value
                    if dynamic_position_sizing:
                        open_trades_value[symbol] = capital_for_trade

                elif is_buy and last_trade is not None:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": False,
                        "reason": "already_in_position",
                    })

            # Update open trade values at each timestamp for
            # accurate portfolio value
            if dynamic_position_sizing:
                for symbol, data in symbol_data.items():
                    if data['last_trade'] is not None:
                        current_price = float(data['close'].iloc[i])
                        open_trades_value[symbol] = (
                            data['last_trade'].available_amount * current_price
                        )

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
        # Issue 8: Store raw signals for analysis
        raw_signals = {}
        for symbol in buy_signals.keys():
            raw_signals[symbol] = {
                "buy": buy_signals[symbol],
                "sell": sell_signals[symbol],
            }

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
                backtest_date_range.end_date - backtest_date_range.start_date
            ).days,
            number_of_trades=len(trades),
            number_of_orders=len(orders),
            number_of_trades_closed=number_of_trades_closed,
            number_of_trades_open=number_of_trades_open,
            number_of_positions=len(unique_symbols),
            symbols=list(buy_signals.keys()),
            signals=raw_signals,
            signal_events=signal_events,
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
