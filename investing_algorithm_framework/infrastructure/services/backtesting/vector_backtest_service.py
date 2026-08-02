from datetime import datetime, timezone
from uuid import uuid4

import logging

import pandas as pd

from investing_algorithm_framework.domain import BacktestDateRange, \
    BacktestRun, BacktestWindow, Portfolio, TimeFrame, PortfolioConfiguration, \
    PortfolioSnapshot, OperationalException, Order, OrderType, OrderStatus, \
    OrderSide, Trade, TradeStatus, DataType, TradingCost, CooldownTracker, \
    SignalSide
from investing_algorithm_framework.services import DataProviderService, \
    create_backtest_metrics
from investing_algorithm_framework.services.pipeline import \
    VectorPipelineEngine


logger = logging.getLogger(__name__)


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
            data starting from ``start_date - warmup_window * timeframe``
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

        # Phase 2 (#502): inject pipeline outputs into ``data`` before
        # the strategy's vectorised signal generators are called. Each
        # pipeline is evaluated once over the entire backtest window
        # and exposed as a long-form ``polars.DataFrame`` keyed by the
        # pipeline class name (mirroring event-mode behaviour, except
        # the frame is long instead of single-bar wide because vector
        # signals consume the full window).
        self._inject_pipelines(
            strategy=strategy,
            data=data,
            backtest_date_range=backtest_date_range,
        )

        # Compute signals from strategy via the v9.0 SignalSeries
        # protocol. The strategy yields one SignalSeries per
        # (symbol, side) pair; we bucket them back into the six
        # per-side dicts the downstream per-bar loop already speaks.
        # Strategies that target the vector engine must override
        # ``generate_signal_series(data)``; see
        # docs/migration-v8-to-v9.md §10.
        (
            buy_signals,
            sell_signals,
            scale_in_signals,
            scale_out_signals,
            short_signals,
            cover_signals,
        ) = self._bucket_signal_series(
            strategy.generate_signal_series(data)
        )
        shorting_enabled = (
            short_signals is not None and cover_signals is not None
        )

        # Generate optional recorded values
        raw_recorded = strategy.generate_recorded_values(data)

        if scale_in_signals is None:
            scale_in_signals = buy_signals

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
        scale_in_signals = {k: v[v.index >= backtest_date_range.start_date]
                            for k, v in scale_in_signals.items()}
        if scale_out_signals is not None:
            scale_out_signals = {
                k: v[v.index >= backtest_date_range.start_date]
                for k, v in scale_out_signals.items()
            }
        if shorting_enabled:
            short_signals = {
                k: v[v.index >= backtest_date_range.start_date]
                for k, v in short_signals.items()
            }
            cover_signals = {
                k: v[v.index >= backtest_date_range.start_date]
                for k, v in cover_signals.items()
            }

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
        # v9.0 (#433) — iterate the union of all signal dicts so
        # short-only strategies (no OPEN_LONG signals) still get a
        # symbol_data entry. Previously iterating only
        # ``buy_signals.keys()`` silently dropped every symbol that had
        # exclusively SHORT / COVER signals.
        all_signal_symbols = set(buy_signals.keys()) \
            | set(sell_signals.keys()) \
            | set(scale_in_signals.keys() if scale_in_signals else [])
        if scale_out_signals is not None:
            all_signal_symbols |= set(scale_out_signals.keys())
        if shorting_enabled:
            all_signal_symbols |= set(short_signals.keys())
            all_signal_symbols |= set(cover_signals.keys())
        for symbol in all_signal_symbols:
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
            # v9.0 (#433) — default to all-False when this symbol
            # only emits SHORT / COVER signals.
            buy_signal = buy_signals[symbol].reindex(
                index, fill_value=False
            ) if symbol in buy_signals else pd.Series(False, index=index)
            sell_signal = sell_signals[symbol].reindex(
                index, fill_value=False
            ) if symbol in sell_signals else pd.Series(False, index=index)

            # Align scale-in / scale-out signals
            si_signal = scale_in_signals[symbol].reindex(
                index, fill_value=False
            ) if symbol in scale_in_signals else pd.Series(
                False, index=index
            )
            so_signal = pd.Series(False, index=index)
            if (scale_out_signals is not None
                    and symbol in scale_out_signals):
                so_signal = scale_out_signals[symbol].reindex(
                    index, fill_value=False
                )

            # Align SHORT / COVER signals (#433). Defaults to all-False
            # series when shorting is disabled so the per-bar branches
            # remain cheap.
            short_signal = pd.Series(False, index=index)
            cover_signal = pd.Series(False, index=index)
            if shorting_enabled:
                if symbol in short_signals:
                    short_signal = short_signals[symbol].reindex(
                        index, fill_value=False
                    )
                if symbol in cover_signals:
                    cover_signal = cover_signals[symbol].reindex(
                        index, fill_value=False
                    )

            # Find the ScalingRule for this symbol, if any
            scaling_rule = None
            if hasattr(strategy, 'scaling_rules') and strategy.scaling_rules:
                scaling_rule = next(
                    (sr for sr in strategy.scaling_rules
                     if sr.symbol == symbol),
                    None
                )

            # Resolve TradingCost for this symbol
            trading_cost = TradingCost.resolve(
                symbol,
                getattr(strategy, 'trading_costs', None),
                portfolio_configuration,
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
                'scale_in_signal': si_signal,
                'scale_out_signal': so_signal,
                'short_signal': short_signal,
                'cover_signal': cover_signal,
                'scaling_rule': scaling_rule,
                'trading_cost': trading_cost,
                'initial_capital_for_trade': initial_capital_for_trade,
                'last_trade': None,  # Track open trade per symbol
                'open_trades': [],   # All open trades for this symbol
                'is_short': False,   # True iff last_trade is a short (#433)
                'cooldown_remaining': 0,  # Bars remaining in cooldown
                'scale_out_count': 0,     # Number of scale-outs done
                'entry_count': 0,         # Number of entries so far
            }

        # Signal event log — records every fired signal and its outcome
        signal_events = []

        # Portfolio-scoped cooldown tracker for CooldownRule evaluation.
        # Shared across symbols so portfolio-scoped rules (symbol=None) work.
        cooldown_tracker = CooldownTracker()
        strategy_cooldowns = list(getattr(strategy, 'cooldowns', None) or [])

        # Shared portfolio state for dynamic position sizing
        current_unallocated = initial_amount
        total_realized_gains = 0.0
        total_allocated = 0.0  # Track total allocated in static mode
        open_trades_value = {}  # Track value of open trades per symbol

        # Pre-compute scheduled external deposits (e.g. monthly paychecks)
        # for the backtest window. Vector backtests are single-pass and
        # have no Context, so we eagerly resolve the full schedule into a
        # sorted (timestamp, amount) list and credit ``current_unallocated``
        # the first bar at-or-after each timestamp. Net effect for the
        # strategy: the simulated broker balance grows on cadence, and the
        # equity curve / metrics include the external cash flows just like
        # the event backtest does after a sync_portfolio call.
        deposit_events = self._resolve_deposit_schedule(
            portfolio_configuration=portfolio_configuration,
            backtest_date_range=backtest_date_range,
        )
        deposit_event_idx = 0

        def _close_trade(sym, sym_data, price, date):
            """Helper to close an open trade for a symbol."""
            nonlocal current_unallocated, total_realized_gains, \
                total_allocated

            lt = sym_data['last_trade']
            tc = sym_data['trading_cost']
            sell_fill = tc.get_sell_fill_price(price)
            gross = sell_fill * lt.available_amount
            sell_fee = tc.get_fee(gross)
            net_gain_val = gross - sell_fee - lt.cost

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
                price=sell_fill,
                amount=lt.available_amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.SELL,
                order_fee=sell_fee,
                order_fee_rate=tc.fee_percentage / 100
                if tc.fee_percentage else None,
                slippage=price - sell_fill,
                metadata={"order_reason": "sell_signal"},
            )
            orders.append(sell_order)
            trade_orders = lt.orders
            trade_orders.append(sell_order)

            lt_total_fees = (lt.total_fees or 0) + sell_fee
            lt.update(
                {
                    "orders": trade_orders,
                    "closed_at": date,
                    "status": TradeStatus.CLOSED.value,
                    "updated_at": date,
                    "net_gain": net_gain_val,
                    "total_fees": lt_total_fees,
                }
            )
            sym_data['last_trade'] = None
            # Close all open trades when fully exiting
            for ot in sym_data['open_trades']:
                if ot.id != lt.id and TradeStatus.OPEN.equals(ot.status):
                    ot_gross = ot.available_amount * sell_fill
                    ot_sell_fee = tc.get_fee(ot_gross)
                    ot_gain = ot_gross - ot_sell_fee - ot.cost
                    sell_o = Order(
                        id=uuid4(),
                        target_symbol=sym,
                        trading_symbol=trading_symbol,
                        order_type=OrderType.LIMIT,
                        price=sell_fill,
                        amount=ot.available_amount,
                        status=OrderStatus.CLOSED,
                        created_at=date,
                        updated_at=date,
                        order_side=OrderSide.SELL,
                        order_fee=ot_sell_fee,
                        order_fee_rate=tc.fee_percentage / 100
                        if tc.fee_percentage else None,
                        slippage=price - sell_fill,
                        metadata={"order_reason": "sell_signal"},
                    )
                    orders.append(sell_o)
                    ot_orders = ot.orders
                    ot_orders.append(sell_o)
                    ot_total_fees = (ot.total_fees or 0) + ot_sell_fee
                    ot.update({
                        "orders": ot_orders,
                        "closed_at": date,
                        "status": TradeStatus.CLOSED.value,
                        "updated_at": date,
                        "net_gain": ot_gain,
                        "total_fees": ot_total_fees,
                    })
                    if dynamic_position_sizing:
                        current_unallocated += ot.cost + ot_gain
                        total_realized_gains += ot_gain
                    else:
                        total_allocated -= ot.cost
            sym_data['open_trades'] = []
            sym_data['entry_count'] = 0
            sym_data['scale_out_count'] = 0

        def _open_trade(
            sym, sym_data, price, date, capital,
            order_reason="buy_signal"
        ):
            """Helper to open a new trade for a symbol."""
            nonlocal current_unallocated, total_allocated

            tc = sym_data['trading_cost']
            fill_price = tc.get_buy_fill_price(price)

            # Fee comes out of capital; remainder buys the asset
            buy_fee = tc.get_fee(capital)
            net_capital = capital - buy_fee

            if net_capital <= 0:
                return None

            amount = float(net_capital / fill_price)

            if dynamic_position_sizing:
                current_unallocated -= capital
            else:
                total_allocated += capital

            buy_order = Order(
                id=uuid4(),
                target_symbol=sym,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT,
                price=fill_price,
                amount=amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.BUY,
                order_fee=buy_fee,
                order_fee_rate=tc.fee_percentage / 100
                if tc.fee_percentage else None,
                slippage=fill_price - price,
                metadata={"order_reason": order_reason},
            )
            orders.append(buy_order)
            trade = Trade(
                id=uuid4(),
                orders=[buy_order],
                target_symbol=sym,
                trading_symbol=trading_symbol,
                available_amount=amount,
                remaining=0,
                filled_amount=amount,
                open_price=fill_price,
                opened_at=date,
                closed_at=None,
                amount=amount,
                status=TradeStatus.OPEN.value,
                cost=net_capital,
                total_fees=buy_fee,
            )
            sym_data['last_trade'] = trade
            sym_data['open_trades'].append(trade)
            sym_data['entry_count'] += 1
            trades.append(trade)

            if dynamic_position_sizing:
                open_trades_value[sym] = \
                    open_trades_value.get(sym, 0) + net_capital

            return trade

        def _get_capital_for_trade(sym_data, price, pct_of_base=100):
            """Calculate capital for a trade, respecting portfolio limits."""
            pos_size_obj = sym_data['pos_size_obj']
            if dynamic_position_sizing:
                open_total = sum(open_trades_value.values())
                portfolio_value = current_unallocated + open_total
                base = pos_size_obj.get_size(
                    Portfolio(
                        unallocated=portfolio_value,
                        initial_balance=initial_amount,
                        trading_symbol=trading_symbol,
                        net_size=0,
                        market="BACKTEST",
                        identifier="vector_backtest"
                    ),
                    asset_price=price
                )
                capital = base * pct_of_base / 100
                return min(capital, current_unallocated)
            else:
                base = sym_data['initial_capital_for_trade']
                capital = base * pct_of_base / 100
                if total_allocated + capital > initial_amount:
                    return 0
                return capital

        def _partial_close(sym, sym_data, price, date, sell_pct):
            """Partial close of the most recent open trade."""
            nonlocal current_unallocated, total_realized_gains, \
                total_allocated

            lt = sym_data['last_trade']
            if lt is None:
                return

            tc = sym_data['trading_cost']
            sell_amount = lt.available_amount * sell_pct / 100
            if sell_amount <= 0:
                return

            sell_fill = tc.get_sell_fill_price(price)

            # Proportional cost (fraction of total cost)
            sell_cost = lt.cost * (sell_amount / lt.available_amount)
            gross = sell_amount * sell_fill
            sell_fee = tc.get_fee(gross)
            net_gain_val = gross - sell_fee - sell_cost

            if dynamic_position_sizing:
                current_unallocated += sell_cost + net_gain_val
                total_realized_gains += net_gain_val
                if sym in open_trades_value:
                    open_trades_value[sym] = max(
                        0, open_trades_value[sym] - sell_cost
                    )
            else:
                total_allocated -= sell_cost

            sell_order = Order(
                id=uuid4(),
                target_symbol=sym,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT,
                price=sell_fill,
                amount=sell_amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.SELL,
                order_fee=sell_fee,
                order_fee_rate=tc.fee_percentage / 100
                if tc.fee_percentage else None,
                slippage=price - sell_fill,
                metadata={"order_reason": "scale_out"},
            )
            orders.append(sell_order)
            trade_orders = lt.orders
            trade_orders.append(sell_order)
            new_available = lt.available_amount - sell_amount
            new_cost = lt.cost - sell_cost
            old_net = lt.net_gain if lt.net_gain else 0.0
            lt_total_fees = (lt.total_fees or 0) + sell_fee
            update_dict = {
                "orders": trade_orders,
                "available_amount": new_available,
                "cost": new_cost,
                "net_gain": old_net + net_gain_val,
                "total_fees": lt_total_fees,
                "updated_at": date,
            }
            if new_available <= 0:
                update_dict["closed_at"] = date
                update_dict["status"] = TradeStatus.CLOSED.value
                sym_data['open_trades'] = [
                    t for t in sym_data['open_trades'] if t.id != lt.id
                ]
                sym_data['last_trade'] = (
                    sym_data['open_trades'][-1]
                    if sym_data['open_trades'] else None
                )
            lt.update(update_dict)

        # ------------------------------------------------------------------
        # SHORT / COVER helpers (#433)
        #
        # A short is a SELL-first / BUY-to-cover trade. Cash mechanics are
        # the mirror of a long: opening a short *credits* unallocated with
        # the sale proceeds; covering *debits* unallocated for the cost to
        # buy the borrowed amount back. P&L therefore equals
        # ``(open_price - cover_price) * amount - fees``.
        #
        # Sizing reuses the existing ``PositionSize`` mechanism: ``capital``
        # (in quote-currency units) is the *notional* committed to the
        # short. We allow the proceeds back into ``unallocated`` only on
        # open; the engine does not currently model margin requirements
        # — vector backtests are a directional-P&L tool.
        # ------------------------------------------------------------------
        def _open_short_trade(
            sym, sym_data, price, date, capital,
            order_reason="short_signal"
        ):
            nonlocal current_unallocated, total_allocated

            tc = sym_data['trading_cost']
            # On a SHORT entry the broker fills our SELL — slippage moves
            # against us in the same direction as a long exit, hence the
            # sell-side fill price.
            fill_price = tc.get_sell_fill_price(price)

            amount = float(capital / fill_price)
            gross_proceeds = amount * fill_price
            short_fee = tc.get_fee(gross_proceeds)
            net_proceeds = gross_proceeds - short_fee

            if amount <= 0 or net_proceeds <= 0:
                return None

            if dynamic_position_sizing:
                # Short entry releases cash into the wallet (proceeds in,
                # fee out).
                current_unallocated += net_proceeds
            else:
                # Static mode still reserves notional against the original
                # budget so a short cannot exceed portfolio capacity.
                total_allocated += capital

            short_order = Order(
                id=uuid4(),
                target_symbol=sym,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT,
                price=fill_price,
                amount=amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.SELL,
                order_fee=short_fee,
                order_fee_rate=tc.fee_percentage / 100
                if tc.fee_percentage else None,
                slippage=price - fill_price,
                metadata={"order_reason": order_reason, "is_short": True},
            )
            orders.append(short_order)
            trade = Trade(
                id=uuid4(),
                orders=[short_order],
                target_symbol=sym,
                trading_symbol=trading_symbol,
                available_amount=amount,
                remaining=0,
                filled_amount=amount,
                open_price=fill_price,
                opened_at=date,
                closed_at=None,
                amount=amount,
                status=TradeStatus.OPEN.value,
                # ``cost`` for a short is the notional (proceeds before
                # fees). This keeps net_gain_percentage and percentage
                # change calculations consistent with the long path.
                cost=gross_proceeds,
                total_fees=short_fee,
                is_short=True,
                metadata={"is_short": True},
            )
            sym_data['last_trade'] = trade
            sym_data['open_trades'].append(trade)
            sym_data['entry_count'] += 1
            sym_data['is_short'] = True
            trades.append(trade)

            if dynamic_position_sizing:
                # Track the short's notional liability so portfolio value
                # computations see the open position. At open the
                # liability matches the gross proceeds, so the residual
                # (proceeds - liability) is ~0 — the per-bar reprice
                # loop updates it as price drifts.
                open_trades_value[sym] = 0.0

            return trade

        def _close_short_trade(sym, sym_data, price, date):
            nonlocal current_unallocated, total_realized_gains, \
                total_allocated

            lt = sym_data['last_trade']
            if lt is None:
                return

            tc = sym_data['trading_cost']
            # Covering = BUY back; pay buy-side slippage.
            cover_fill = tc.get_buy_fill_price(price)
            cover_gross = cover_fill * lt.available_amount
            cover_fee = tc.get_fee(cover_gross)
            # P&L mirror: long is gross_sell - cost - fee; short is
            # proceeds(=cost) - gross_buy - fee.
            net_gain_val = lt.cost - cover_gross - cover_fee

            if dynamic_position_sizing:
                current_unallocated -= (cover_gross + cover_fee)
                total_realized_gains += net_gain_val
                if sym in open_trades_value:
                    del open_trades_value[sym]
            else:
                total_allocated -= lt.cost

            cover_order = Order(
                id=uuid4(),
                target_symbol=sym,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT,
                price=cover_fill,
                amount=lt.available_amount,
                status=OrderStatus.CLOSED,
                created_at=date,
                updated_at=date,
                order_side=OrderSide.BUY,
                order_fee=cover_fee,
                order_fee_rate=tc.fee_percentage / 100
                if tc.fee_percentage else None,
                slippage=cover_fill - price,
                metadata={"order_reason": "cover_signal", "is_cover": True},
            )
            orders.append(cover_order)
            trade_orders = lt.orders
            trade_orders.append(cover_order)

            lt_total_fees = (lt.total_fees or 0) + cover_fee
            lt.update(
                {
                    "orders": trade_orders,
                    "closed_at": date,
                    "status": TradeStatus.CLOSED.value,
                    "updated_at": date,
                    "net_gain": net_gain_val,
                    "total_fees": lt_total_fees,
                }
            )
            sym_data['last_trade'] = None
            sym_data['open_trades'] = []
            sym_data['entry_count'] = 0
            sym_data['scale_out_count'] = 0
            sym_data['is_short'] = False

        # v9.0 (#487) — fixed-percentage TP / SL evaluators for the
        # vector engine. Trailing rules are intentionally NOT supported
        # here yet; strategies that need trailing TP/SL should run in
        # event mode (which uses ``trade_service`` with full state).
        strategy_take_profits = list(
            getattr(strategy, 'take_profits', None) or []
        )
        strategy_stop_losses = list(
            getattr(strategy, 'stop_losses', None) or []
        )

        def _matches_symbol(rule, sym):
            rule_sym = getattr(rule, 'symbol', None)
            return rule_sym is None or rule_sym == sym

        def _tp_triggered(rule, entry_price, current, is_short):
            pct = float(rule.percentage_threshold) / 100.0
            if is_short:
                threshold = entry_price * (1.0 - pct)
                return current <= threshold
            threshold = entry_price * (1.0 + pct)
            return current >= threshold

        def _sl_triggered(rule, entry_price, current, is_short):
            pct = float(rule.percentage_threshold) / 100.0
            if is_short:
                threshold = entry_price * (1.0 + pct)
                return current >= threshold
            threshold = entry_price * (1.0 - pct)
            return current <= threshold

        def _evaluate_tp_sl(sym, sym_data, current_price, current_date, i):
            """Close the open trade if any fixed TP / SL rule has
            triggered against ``current_price``. Returns the reason
            string (``"take_profit"`` / ``"stop_loss"``) or ``None``.
            """
            last = sym_data['last_trade']
            if last is None:
                return None
            entry_price = float(last.open_price)
            is_short = bool(getattr(last, 'is_short', False))
            # Take-profit wins ties with stop-loss to match the event
            # engine's evaluation order.
            for rule in strategy_take_profits:
                if not _matches_symbol(rule, sym):
                    continue
                if getattr(rule, 'trailing', False):
                    continue
                if _tp_triggered(rule, entry_price, current_price, is_short):
                    if is_short:
                        _close_short_trade(
                            sym, sym_data, current_price, current_date
                        )
                    else:
                        _close_trade(
                            sym, sym_data, current_price, current_date
                        )
                    cooldown_tracker.record(
                        symbol=sym,
                        order_side="buy" if is_short else "sell",
                        bar_index=i,
                    )
                    return "take_profit"
            for rule in strategy_stop_losses:
                if not _matches_symbol(rule, sym):
                    continue
                if getattr(rule, 'trailing', False):
                    continue
                if _sl_triggered(rule, entry_price, current_price, is_short):
                    if is_short:
                        _close_short_trade(
                            sym, sym_data, current_price, current_date
                        )
                    else:
                        _close_trade(
                            sym, sym_data, current_price, current_date
                        )
                    cooldown_tracker.record(
                        symbol=sym,
                        order_side="buy" if is_short else "sell",
                        bar_index=i,
                    )
                    return "stop_loss"
            return None

        # Process all timestamps in chronological order
        for i in range(len(index)):
            current_date = index[i]

            # Convert the pd.Timestamp to an utc datetime object
            if isinstance(current_date, pd.Timestamp):
                current_date = current_date.to_pydatetime()

            if current_date.tzinfo is None:
                current_date = current_date.replace(tzinfo=timezone.utc)

            # Apply any scheduled external deposits whose timestamp has
            # been reached by ``current_date``. Each event fires exactly
            # once at the first bar at-or-after its scheduled time.
            while (
                deposit_event_idx < len(deposit_events)
                and deposit_events[deposit_event_idx][0] <= current_date
            ):
                _, deposit_amount = deposit_events[deposit_event_idx]
                current_unallocated += deposit_amount
                deposit_event_idx += 1

            # Process each symbol at this timestamp
            for symbol, data in symbol_data.items():
                current_price = float(data['close'].iloc[i])
                last_trade = data['last_trade']
                scaling_rule = data['scaling_rule']
                has_position = last_trade is not None

                # v9.0 (#487) — evaluate fixed TP / SL before signal
                # processing. A triggered TP/SL closes the open trade
                # for ``symbol`` immediately, records a side-specific
                # cooldown via ``cooldown_tracker``, and emits a
                # ``signal_event`` so downstream tooling can attribute
                # the exit.
                if has_position:
                    tp_sl_reason = _evaluate_tp_sl(
                        symbol, data, current_price, current_date, i
                    )
                    if tp_sl_reason is not None:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": tp_sl_reason,
                            "executed": True,
                            "reason": "executed",
                        })
                        last_trade = data['last_trade']  # now None
                        has_position = False

                # Tick down cooldown
                if data['cooldown_remaining'] > 0:
                    data['cooldown_remaining'] -= 1

                in_cooldown = data['cooldown_remaining'] > 0

                # CooldownRule gating (portfolio-aware, side-specific)
                rule_block_buy, _rule_buy = cooldown_tracker.is_blocked(
                    strategy_cooldowns,
                    signal_side="buy",
                    symbol=symbol,
                    bar_index=i,
                )
                rule_block_sell, _rule_sell = cooldown_tracker.is_blocked(
                    strategy_cooldowns,
                    signal_side="sell",
                    symbol=symbol,
                    bar_index=i,
                )

                # Read raw boolean signals for this bar
                is_buy = bool(data['buy_signal'].iloc[i])
                is_sell = bool(data['sell_signal'].iloc[i])
                is_scale_in = bool(data['scale_in_signal'].iloc[i])
                is_scale_out = bool(data['scale_out_signal'].iloc[i])
                # SHORT / COVER (#433). When shorting is disabled these
                # series are all-False and the branches are no-ops.
                is_short_sig = bool(data['short_signal'].iloc[i])
                is_cover_sig = bool(data['cover_signal'].iloc[i])
                is_short_pos = data['is_short']
                is_long_pos = has_position and not is_short_pos

                # ---- SELL always takes priority (long-only close) ----
                if (is_sell and is_long_pos and not in_cooldown
                        and rule_block_sell):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "sell",
                        "executed": False,
                        "reason": "in_cooldown_rule",
                    })
                elif is_sell and is_long_pos and not in_cooldown:
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
                    last_trade = data['last_trade']
                    has_position = False
                    if scaling_rule and scaling_rule.cooldown_in_bars > 0:
                        data['cooldown_remaining'] = \
                            scaling_rule.cooldown_in_bars
                        in_cooldown = True
                    cooldown_tracker.record(
                        symbol=symbol, order_side="sell", bar_index=i,
                    )
                    rule_block_sell, _ = cooldown_tracker.is_blocked(
                        strategy_cooldowns, signal_side="sell",
                        symbol=symbol, bar_index=i,
                    )
                    rule_block_buy, _ = cooldown_tracker.is_blocked(
                        strategy_cooldowns, signal_side="buy",
                        symbol=symbol, bar_index=i,
                    )
                    # Reset is_buy if sell also fired on same bar
                    is_buy = False
                    is_scale_in = False
                    is_scale_out = False
                elif is_sell and not has_position:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "sell",
                        "executed": False,
                        "reason": "no_position_to_close",
                    })
                elif is_sell and in_cooldown:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "sell",
                        "executed": False,
                        "reason": "in_cooldown",
                    })

                # ---- COVER (close short) — mirror of SELL (#433) ----
                if is_cover_sig and is_short_pos and not in_cooldown:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "cover",
                        "executed": True,
                        "reason": "executed",
                    })
                    _close_short_trade(
                        symbol, data, current_price, current_date
                    )
                    last_trade = data['last_trade']
                    has_position = False
                    is_short_pos = False
                    is_long_pos = False
                    cooldown_tracker.record(
                        symbol=symbol, order_side="buy", bar_index=i,
                    )
                    # A cover on the same bar shouldn't also re-enter
                    # short / long.
                    is_buy = False
                    is_short_sig = False
                elif is_cover_sig and not is_short_pos:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "cover",
                        "executed": False,
                        "reason": "no_short_position_to_cover",
                    })
                elif is_cover_sig and in_cooldown:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "cover",
                        "executed": False,
                        "reason": "in_cooldown",
                    })

                # ---- SCALE-OUT (partial close) ----
                # Scaling rules apply to long positions only.
                if (is_scale_out and is_long_pos
                        and scaling_rule is not None and not in_cooldown
                        and rule_block_sell):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "scale_out",
                        "executed": False,
                        "reason": "in_cooldown_rule",
                    })
                elif (is_scale_out and is_long_pos
                        and scaling_rule is not None and not in_cooldown):
                    so_idx = data['scale_out_count']
                    pct = scaling_rule.get_scale_out_percentage(so_idx)
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "scale_out",
                        "executed": True,
                        "reason": "executed",
                    })
                    _partial_close(
                        symbol, data, current_price, current_date, pct
                    )
                    data['scale_out_count'] += 1
                    last_trade = data['last_trade']
                    has_position = last_trade is not None
                    if scaling_rule.cooldown_in_bars > 0:
                        data['cooldown_remaining'] = \
                            scaling_rule.cooldown_in_bars
                        in_cooldown = True
                    cooldown_tracker.record(
                        symbol=symbol, order_side="sell", bar_index=i,
                    )
                    rule_block_sell, _ = cooldown_tracker.is_blocked(
                        strategy_cooldowns, signal_side="sell",
                        symbol=symbol, bar_index=i,
                    )
                    rule_block_buy, _ = cooldown_tracker.is_blocked(
                        strategy_cooldowns, signal_side="buy",
                        symbol=symbol, bar_index=i,
                    )

                # ---- BUY (new entry) ----
                if (is_buy and not has_position and not in_cooldown
                        and rule_block_buy):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": False,
                        "reason": "in_cooldown_rule",
                    })
                elif is_buy and not has_position and not in_cooldown:
                    capital = _get_capital_for_trade(
                        data, current_price, 100
                    )
                    if capital <= 0:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "buy",
                            "executed": False,
                            "reason": "insufficient_capital",
                        })
                    else:
                        _open_trade(
                            symbol, data, current_price,
                            current_date, capital
                        )
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "buy",
                            "executed": True,
                            "reason": "executed",
                        })
                        if scaling_rule and \
                                scaling_rule.cooldown_in_bars > 0:
                            data['cooldown_remaining'] = \
                                scaling_rule.cooldown_in_bars
                            in_cooldown = True
                        cooldown_tracker.record(
                            symbol=symbol, order_side="buy", bar_index=i,
                        )
                        rule_block_sell, _ = cooldown_tracker.is_blocked(
                            strategy_cooldowns, signal_side="sell",
                            symbol=symbol, bar_index=i,
                        )
                        rule_block_buy, _ = cooldown_tracker.is_blocked(
                            strategy_cooldowns, signal_side="buy",
                            symbol=symbol, bar_index=i,
                        )
                elif is_buy and is_long_pos and not in_cooldown:
                    # Possible scale-in via buy signal (if no separate
                    # scale_in_signals provided, buy = scale_in)
                    if scaling_rule is not None:
                        is_scale_in = True  # treat as scale-in below
                    else:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "buy",
                            "executed": False,
                            "reason": "already_in_position",
                        })
                elif is_buy and is_short_pos and not in_cooldown:
                    # Buy signals never flip an open short — the
                    # strategy must cover first (#433).
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": False,
                        "reason": "open_short_position",
                    })
                elif is_buy and in_cooldown:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "buy",
                        "executed": False,
                        "reason": "in_cooldown",
                    })

                # ---- SCALE-IN (add to position) ----
                # Scaling rules apply to long positions only.
                if (is_scale_in and is_long_pos
                        and scaling_rule is not None and not in_cooldown
                        and rule_block_buy):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "scale_in",
                        "executed": False,
                        "reason": "in_cooldown_rule",
                    })
                elif (is_scale_in and is_long_pos
                        and scaling_rule is not None and in_cooldown):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "scale_in",
                        "executed": False,
                        "reason": "in_cooldown",
                    })
                elif (is_scale_in and is_long_pos
                        and scaling_rule is not None and not in_cooldown):
                    entry_count = data['entry_count']
                    if entry_count >= scaling_rule.max_entries:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "scale_in",
                            "executed": False,
                            "reason": "max_entries_reached",
                        })
                    else:
                        si_idx = entry_count - 1  # 0-indexed scale-in
                        pct = scaling_rule.get_scale_in_percentage(si_idx)
                        capital = _get_capital_for_trade(
                            data, current_price, pct
                        )
                        if capital <= 0:
                            signal_events.append({
                                "date": current_date,
                                "symbol": symbol,
                                "signal": "scale_in",
                                "executed": False,
                                "reason": "insufficient_capital",
                            })
                        else:
                            _open_trade(
                                symbol, data, current_price,
                                current_date, capital,
                                order_reason="scale_in"
                            )
                            signal_events.append({
                                "date": current_date,
                                "symbol": symbol,
                                "signal": "scale_in",
                                "executed": True,
                                "reason": "executed",
                            })
                            if scaling_rule.cooldown_in_bars > 0:
                                data['cooldown_remaining'] = \
                                    scaling_rule.cooldown_in_bars
                            cooldown_tracker.record(
                                symbol=symbol, order_side="buy",
                                bar_index=i,
                            )

                # ---- SHORT (open short, #433) ----
                # Open a new short only when flat. Buy signals on the
                # same bar take priority because an opened long already
                # consumed ``has_position``; check both to be defensive.
                if (is_short_sig and not has_position
                        and not in_cooldown and rule_block_sell):
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "short",
                        "executed": False,
                        "reason": "in_cooldown_rule",
                    })
                elif (is_short_sig and not has_position
                        and not in_cooldown):
                    capital = _get_capital_for_trade(
                        data, current_price, 100
                    )
                    if capital <= 0:
                        signal_events.append({
                            "date": current_date,
                            "symbol": symbol,
                            "signal": "short",
                            "executed": False,
                            "reason": "insufficient_capital",
                        })
                    else:
                        opened = _open_short_trade(
                            symbol, data, current_price,
                            current_date, capital,
                        )
                        if opened is not None:
                            signal_events.append({
                                "date": current_date,
                                "symbol": symbol,
                                "signal": "short",
                                "executed": True,
                                "reason": "executed",
                            })
                            cooldown_tracker.record(
                                symbol=symbol, order_side="sell",
                                bar_index=i,
                            )
                elif is_short_sig and has_position:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "short",
                        "executed": False,
                        "reason": "already_in_position",
                    })
                elif is_short_sig and in_cooldown:
                    signal_events.append({
                        "date": current_date,
                        "symbol": symbol,
                        "signal": "short",
                        "executed": False,
                        "reason": "in_cooldown",
                    })

            # Update open trade values at each timestamp for
            # accurate portfolio value
            if dynamic_position_sizing:
                for symbol, data in symbol_data.items():
                    if data['open_trades']:
                        current_price = float(data['close'].iloc[i])
                        if data['is_short']:
                            # For shorts the proceeds are already in
                            # ``current_unallocated``; this slot holds
                            # the residual = proceeds - live liability
                            # so total portfolio value = unallocated +
                            # sum(open_trades_value) stays correct.
                            liability = sum(
                                t.available_amount * current_price
                                for t in data['open_trades']
                                if TradeStatus.OPEN.equals(t.status)
                            )
                            proceeds = sum(
                                t.cost
                                for t in data['open_trades']
                                if TradeStatus.OPEN.equals(t.status)
                            )
                            open_trades_value[symbol] = proceeds - liability
                        else:
                            open_trades_value[symbol] = sum(
                                t.available_amount * current_price
                                for t in data['open_trades']
                                if TradeStatus.OPEN.equals(t.status)
                            )

        unallocated = initial_amount
        total_net_gain = 0.0
        open_trades = []
        # Replay deposit events for snapshot bookkeeping. Each snapshot
        # gets ``cash_flow`` set to whatever external cash landed between
        # the previous snapshot and this one — this is what enables
        # TWR-aware return metrics (CAGR, monthly/yearly returns) to
        # subtract external deposits before computing returns.
        deposit_replay_idx = 0

        # Create portfolio snapshots
        for ts in index:
            allocated = 0
            interval_datetime = pd.Timestamp(ts).to_pydatetime()
            interval_datetime = interval_datetime.replace(tzinfo=timezone.utc)

            # Apply any deposits that fired between the previous snapshot
            # and this one, accumulating them into snapshot_cash_flow.
            snapshot_cash_flow = 0.0
            while (
                deposit_replay_idx < len(deposit_events)
                and deposit_events[deposit_replay_idx][0] <= interval_datetime
            ):
                _, deposit_amount = deposit_events[deposit_replay_idx]
                unallocated += deposit_amount
                snapshot_cash_flow += deposit_amount
                deposit_replay_idx += 1

            for trade in trades:

                if trade.opened_at == interval_datetime:
                    if trade.is_short:
                        # Short entry credits the wallet with sale
                        # proceeds (#433).
                        unallocated += trade.cost
                    else:
                        # Snapshot taken at the moment a trade is opened
                        unallocated -= trade.cost
                    open_trades.append(trade)

                if trade.closed_at == interval_datetime:
                    if trade.is_short:
                        # Covering pays cover_cost = cost - net_gain
                        # back out of unallocated.
                        unallocated -= (trade.cost - trade.net_gain)
                    else:
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

                if open_trade.is_short:
                    # Open short = liability of ``amount * current_price``
                    # against the proceeds already in unallocated.
                    allocated -= open_trade.filled_amount * price
                else:
                    allocated += open_trade.filled_amount * price

            # total_value = invested_value + unallocated
            # total_net_gain = total_value - initial_amount - sum(cash_flow)
            snapshots.append(
                PortfolioSnapshot(
                    portfolio_id=portfolio.identifier,
                    created_at=interval_datetime,
                    unallocated=unallocated,
                    total_value=unallocated + allocated,
                    total_net_gain=total_net_gain,
                    cash_flow=snapshot_cash_flow,
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

            if scale_in_signals and symbol in scale_in_signals:
                raw_signals[symbol]["scale_in"] = scale_in_signals[symbol]

            if scale_out_signals and symbol in scale_out_signals:
                raw_signals[symbol]["scale_out"] = \
                    scale_out_signals[symbol]

            if shorting_enabled and symbol in short_signals:
                raw_signals[symbol]["short"] = short_signals[symbol]
            if shorting_enabled and symbol in cover_signals:
                raw_signals[symbol]["cover"] = cover_signals[symbol]

        # Create a backtest run object
        run = BacktestRun(
            initial_unallocated=initial_amount,
            number_of_runs=1,
            portfolio_snapshots=snapshots,
            trades=trades,
            orders=orders,
            positions=[],
            created_at=datetime.now(timezone.utc),
            backtest_window=BacktestWindow(train_range=backtest_date_range),
            number_of_days=(
                backtest_date_range.end_date - backtest_date_range.start_date
            ).days,
            number_of_trades=len(trades),
            number_of_orders=len(orders),
            number_of_trades_closed=number_of_trades_closed,
            number_of_trades_open=number_of_trades_open,
            number_of_positions=len(unique_symbols),
            signals=raw_signals,
            signal_events=signal_events,
            recorded_values=self._convert_recorded_values(raw_recorded),
        )

        # Create backtest metrics
        run.backtest_metrics = create_backtest_metrics(
            run, risk_free_rate=risk_free_rate
        )
        return run

    @staticmethod
    def _bucket_signal_series(signal_series_iterable):
        """Bucket a stream of :class:`SignalSeries` into per-side dicts.

        The vector backtest engine's per-bar loop is structured
        around six per-side dicts (``buy_signals``, ``sell_signals``,
        ``scale_in_signals``, ``scale_out_signals``, ``short_signals``,
        ``cover_signals``). The v9.0 strategy surface emits a single
        flat stream of :class:`SignalSeries`. This helper translates
        between the two without changing downstream code.

        For a given symbol the *last* SignalSeries for a given side
        wins (strategies are expected to emit at most one per pair).
        ``scale_in_signals`` defaults to ``buy_signals`` if the
        strategy emits no SCALE_IN series, matching legacy semantics.
        ``short_signals`` / ``cover_signals`` are returned as ``None``
        when no SignalSeries with the corresponding side was emitted,
        which the downstream loop interprets as "shorting disabled".

        Args:
            signal_series_iterable: Result of
                ``strategy.generate_signal_series(data)``.

        Returns:
            tuple: ``(buy, sell, scale_in, scale_out, short, cover)``
            where each element is either ``Dict[str, pd.Series]`` or
            ``None`` (for the optional short/cover/scale_out pair).
        """
        per_side: dict = {side: {} for side in SignalSide}

        for series in signal_series_iterable:
            per_side[series.side][series.symbol] = series.series

        buy = per_side[SignalSide.OPEN_LONG]
        sell = per_side[SignalSide.CLOSE_LONG]
        scale_in = (
            per_side[SignalSide.SCALE_IN]
            if per_side[SignalSide.SCALE_IN] else None
        )
        scale_out = (
            per_side[SignalSide.SCALE_OUT]
            if per_side[SignalSide.SCALE_OUT] else None
        )
        short = (
            per_side[SignalSide.OPEN_SHORT]
            if per_side[SignalSide.OPEN_SHORT] else None
        )
        cover = (
            per_side[SignalSide.CLOSE_SHORT]
            if per_side[SignalSide.CLOSE_SHORT] else None
        )

        return buy, sell, scale_in, scale_out, short, cover

    @staticmethod
    def _resolve_deposit_schedule(
        portfolio_configuration,
        backtest_date_range,
    ):
        """Materialise a portfolio's deposit schedule for the backtest window.

        Returns a chronologically sorted list of ``(timestamp, amount)``
        tuples. Empty when the configuration has no schedule.
        """
        schedule = list(
            getattr(portfolio_configuration, "deposit_schedule", []) or []
        )
        if not schedule:
            return []
        # Local import to avoid a circular import between domain and
        # infrastructure layers.
        from investing_algorithm_framework.services.portfolios \
            .broker_balance_tracker import BrokerBalanceTracker
        tracker = BrokerBalanceTracker()
        market = portfolio_configuration.market
        tracker.set_schedule(market, schedule)
        return tracker.project_total(
            market=market,
            start=backtest_date_range.start_date,
            end=backtest_date_range.end_date,
        )

    @staticmethod
    def _convert_recorded_values(raw_recorded):
        """
        Convert recorded values from pandas Series to list-of-tuples format.

        Args:
            raw_recorded: Dict[str, pd.Series] or None from
                strategy.generate_recorded_values().

        Returns:
            Dict[str, List[Tuple[datetime, Any]]]: Converted values.
        """
        if raw_recorded is None:
            return {}

        recorded_values = {}
        for key, series in raw_recorded.items():
            entries = []
            for ts, val in series.items():
                dt = ts
                if isinstance(dt, pd.Timestamp):
                    dt = dt.to_pydatetime()
                if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                entries.append((dt, val))
            recorded_values[key] = entries
        return recorded_values

    @staticmethod
    def _inject_pipelines(
        strategy,
        data,
        backtest_date_range: BacktestDateRange,
    ):
        """Compute cross-sectional pipelines once over the backtest
        window and inject their long-form output into ``data``.

        Strategies without ``pipelines`` skip this entirely (zero cost).
        Per Phase 2 of the Pipeline API (#502); see
        ``docs/architecture/strategy/pipeline-api.md``.

        ``data[pipeline_cls.__name__]`` is set to a long-form
        ``polars.DataFrame`` with columns
        ``(datetime, symbol, *factor_columns)``. The dataset spans the
        entire panel (warmup included) but is bounded above at
        ``backtest_date_range.end_date`` to guarantee no look-ahead.
        Use the ``datetime`` column to slice per bar inside your
        signal generators.
        """
        pipelines = getattr(strategy, "pipelines", None)
        if not pipelines:
            return

        # Map symbol -> data-source identifier from the strategy's
        # OHLCV data sources. Mirrors the eventloop logic so the same
        # mapping rules apply in both modes.
        symbol_to_identifier = {}
        for ds in strategy.data_sources or []:
            if not DataType.OHLCV.equals(ds.data_type):
                continue
            if ds.symbol is None or ds.symbol in symbol_to_identifier:
                continue
            symbol_to_identifier[ds.symbol] = ds.get_identifier()

        if not symbol_to_identifier:
            logger.warning(
                "Strategy declares pipelines but has no OHLCV data "
                "sources to feed them; pipelines will be skipped."
            )
            return

        engine = VectorPipelineEngine()
        for pipeline_cls in pipelines:
            try:
                output = engine.evaluate_window(
                    pipeline_cls=pipeline_cls,
                    data_object=data,
                    symbol_to_identifier=symbol_to_identifier,
                    end=backtest_date_range.end_date,
                )
            except Exception:
                logger.exception(
                    "Pipeline %s failed during vector evaluation",
                    pipeline_cls.__name__,
                )
                raise
            data[pipeline_cls.__name__] = output

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
            TimeFrame.TWO_MINUTE: 2,
            TimeFrame.THREE_MINUTE: 3,
            TimeFrame.FOUR_MINUTE: 4,
            TimeFrame.FIVE_MINUTE: 5,
            TimeFrame.TEN_MINUTE: 10,
            TimeFrame.FIFTEEN_MINUTE: 15,
            TimeFrame.TWENTY_MINUTE: 20,
            TimeFrame.THIRTY_MINUTE: 30,
            TimeFrame.ONE_HOUR: 60,
            TimeFrame.TWO_HOUR: 120,
            TimeFrame.FOUR_HOUR: 240,
            TimeFrame.SIX_HOUR: 360,
            TimeFrame.EIGHT_HOUR: 480,
            TimeFrame.TWELVE_HOUR: 720,
            TimeFrame.ONE_DAY: 1440,
            TimeFrame.THREE_DAY: 4320,
            TimeFrame.ONE_WEEK: 10080,
            TimeFrame.ONE_MONTH: 43200,
            TimeFrame.ONE_YEAR: 525600,
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
