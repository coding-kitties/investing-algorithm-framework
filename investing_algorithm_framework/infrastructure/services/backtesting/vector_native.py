"""Native netting accounting and Python domain-object materialization."""
from datetime import timezone
import math
import sys
from uuid import uuid4

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import (
    TradingCost, PositionSize, Order, OrderType, OrderStatus, OrderSide,
    Trade, TradeStatus, PortfolioSnapshot, PositionSnapshot, CooldownRule,
    TakeProfitRule, StopLossRule,
)


class NativeExecutionUnsupported(ValueError):
    """Execution requires a feature outside the native subset."""


def native_events(symbol_data, rows, initial_amount, strategy, *,
                  dynamic_position_sizing, hedge_mode, deposit_events,
                  index=None):
    if hedge_mode:
        raise NativeExecutionUnsupported(
            "Native execution currently requires netting"
        )
    if dynamic_position_sizing and (
        sys.implementation.name != 'cpython' or sys.version_info < (3, 12)
    ):
        raise NativeExecutionUnsupported(
            "Native dynamic sizing matches CPython 3.12+ float summation"
        )
    if getattr(strategy, 'scaling_rules', None):
        raise NativeExecutionUnsupported(
            "Native execution does not support scaling"
        )
    if not math.isfinite(initial_amount) or initial_amount < 0:
        raise NativeExecutionUnsupported("Initial capital must be finite")
    if isinstance(initial_amount, int) and abs(initial_amount) > 2 ** 53:
        raise NativeExecutionUnsupported("Initial capital exceeds f64 range")
    prices, signals, specs = [], [], []
    for data in symbol_data.values():
        cost = data['trading_cost']
        if type(cost) is not TradingCost or cost.slippage_model is not None:
            raise NativeExecutionUnsupported(
                "Native execution requires the standard trading cost model"
            )
        costs = (cost.fee_percentage, cost.fee_fixed, cost.slippage_percentage)
        if (any(not math.isfinite(value) or value < 0 for value in costs)
                or cost.slippage_percentage >= 100):
            raise NativeExecutionUnsupported("Unsupported trading costs")
        raw_capital = data['initial_capital_for_trade']
        if isinstance(raw_capital, int) and abs(raw_capital) > 2 ** 53:
            raise NativeExecutionUnsupported(
                "Static capital exceeds f64 range"
            )
        capital = float(raw_capital)
        if (not math.isfinite(capital) or capital < 0
                or not math.isfinite(capital * 100)):
            raise NativeExecutionUnsupported("Unsupported static capital")
        size = data['pos_size_obj']
        if type(size) is not PositionSize:
            raise NativeExecutionUnsupported("Custom sizing requires Python")
        sizing = (size.fixed_amount, size.percentage_of_portfolio)
        if (all(value is None for value in sizing)
                or any(value is not None and (
                    not math.isfinite(value) or value < 0
                    or (isinstance(value, int) and value > 2 ** 53)
                ) for value in sizing)):
            raise NativeExecutionUnsupported("Unsupported position sizing")
        close = data['close']
        if (not isinstance(close, np.ndarray) or close.dtype != np.float64
                or close.shape != (rows,) or not np.isfinite(close).all()
                or (close <= 0).any()):
            raise NativeExecutionUnsupported(
                "Native prices must be finite positive float64 arrays"
            )
        with np.errstate(over='ignore', under='ignore'):
            amounts = (capital * 100 / 100) / close
        if (not np.isfinite(amounts).all()
                or (capital > 0 and (amounts == 0).any())):
            raise NativeExecutionUnsupported("Unsupported quantity range")
        mask = np.zeros(rows, dtype=np.uint8)
        for bit, name in enumerate((
            'buy_signal', 'sell_signal', 'short_signal', 'cover_signal',
            'scale_in_signal', 'scale_out_signal',
        )):
            values = data[name]
            if (not isinstance(values, np.ndarray)
                    or values.dtype != np.bool_ or values.shape != (rows,)):
                raise NativeExecutionUnsupported(
                    "Native signals must be nonnullable boolean arrays"
                )
            if bit < 4:
                mask |= values.astype(np.uint8) << bit
        if ((mask & 5) == 5).any():
            raise NativeExecutionUnsupported(
                "Simultaneous long/short entries require Python execution"
            )
        prices.append(close.astype('<f8', copy=False).tobytes())
        signals.append(mask.tobytes())
        specs.append((capital, *sizing, *costs))
    deposits = []
    cooldowns = []
    symbols = {symbol: slot for slot, symbol in enumerate(symbol_data)}
    risks = [[] for _ in symbols]
    for name, rule_type, take_profit in (
        ('take_profits', TakeProfitRule, True),
        ('stop_losses', StopLossRule, False),
    ):
        for rule in getattr(strategy, name, None) or ():
            if type(rule) is not rule_type or rule.trailing:
                raise NativeExecutionUnsupported(
                    "Custom or trailing risk rules require Python"
                )
            threshold = float(rule.percentage_threshold)
            if not math.isfinite(threshold) or threshold < 0:
                raise NativeExecutionUnsupported("Unsupported risk threshold")
            for symbol, slot in symbols.items():
                if rule.symbol is None or rule.symbol == symbol:
                    risks[slot].append((take_profit, threshold))
    sides = {'buy': 0, 'sell': 1, 'any': 2}
    for rule in getattr(strategy, 'cooldowns', None) or ():
        if type(rule) is not CooldownRule:
            raise NativeExecutionUnsupported("Custom cooldown requires Python")
        if rule.symbol is not None and rule.symbol not in symbols:
            continue
        if not isinstance(rule.bars, int) or not 0 <= rule.bars <= sys.maxsize:
            raise NativeExecutionUnsupported("Unsupported cooldown duration")
        cooldowns.append((symbols.get(rule.symbol), sides[rule.trigger.value],
                          sides[rule.blocks.value], rule.bars))
    if deposit_events:
        if index is None:
            raise NativeExecutionUnsupported("Deposits require a time index")
        timestamps = pd.DatetimeIndex(index)
        if timestamps.tz is None:
            timestamps = timestamps.tz_localize('UTC')
        for timestamp, amount in deposit_events:
            if not math.isfinite(amount):
                raise NativeExecutionUnsupported("Deposit must be finite")
            deposits.append((int(timestamps.searchsorted(timestamp)), amount))
    import iaf_confluence_native as native

    if getattr(native, 'NETTING_SEMANTICS_VERSION', None) != (
        'netting-accounting-v5'
    ):
        raise NativeExecutionUnsupported("Native execution version mismatch")
    return native.run_netting(
        prices, signals, specs,
        (rows, float(initial_amount), dynamic_position_sizing,
         bool(getattr(strategy, 'flip_on_opposite_signal', False))), deposits,
        (cooldowns, risks),
    )


def materialize_executions(
    events, symbol_data, index, trading_symbol, strategy,
    signal_recorder=None,
):
    symbols = list(symbol_data)
    trades, orders = [], []
    signals = signal_recorder if signal_recorder is not None else []
    active = {}
    sides = ('buy', 'sell', 'short', 'cover')
    reasons = (
        'executed', 'no_position_to_close', 'no_short_position_to_cover',
        'insufficient_capital', 'already_in_position', 'open_short_position',
        'flip_on_opposite_signal',
        'in_cooldown_rule',
        'executed', 'executed',
    )
    order_reasons = (
        'buy_signal', 'sell_signal', 'short_signal', 'cover_signal',
    )
    for event in events:
        symbol = symbols[event.symbol]
        date = pd.Timestamp(index[event.row]).to_pydatetime()
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if event.has_fill:
            opening = event.side in (0, 2)
            short = event.side in (2, 3)
            metadata = {'order_reason': order_reasons[event.side]}
            if short:
                metadata['is_short' if opening else 'is_cover'] = True
            rate = symbol_data[symbol]['trading_cost'].fee_percentage
            order = Order(
                id=uuid4(), target_symbol=symbol,
                trading_symbol=trading_symbol,
                order_type=OrderType.LIMIT, price=event.price,
                amount=event.amount, status=OrderStatus.CLOSED,
                created_at=date, updated_at=date,
                order_side=(OrderSide.BUY if event.side in (0, 3)
                            else OrderSide.SELL),
                order_fee=event.fee,
                order_fee_rate=rate / 100 if rate else None,
                slippage=event.slippage, metadata=metadata,
                strategy_id=(getattr(strategy, 'strategy_id', None)
                             if opening else None),
            )
            orders.append(order)
            if opening:
                extra = ({'is_short': True, 'metadata': {'is_short': True}}
                         if short else {})
                trade = Trade(
                    id=uuid4(), orders=[order], target_symbol=symbol,
                    trading_symbol=trading_symbol,
                    available_amount=event.amount, remaining=0,
                    filled_amount=event.amount, open_price=event.price,
                    opened_at=date, closed_at=None, amount=event.amount,
                    status=TradeStatus.OPEN.value, cost=event.cost,
                    total_fees=event.total_fees, **extra,
                )
                trades.append(trade)
                active[symbol] = trade
            else:
                trade = active.pop(symbol)
                trade.orders.append(order)
                trade.update({
                    'orders': trade.orders, 'closed_at': date,
                    'status': TradeStatus.CLOSED.value, 'updated_at': date,
                    'net_gain': event.net_gain, 'total_fees': event.total_fees,
                })
        signals.append({
            'date': date, 'symbol': symbol,
            'signal': (
                'take_profit' if event.reason == 8 else
                'stop_loss' if event.reason == 9 else sides[event.side]
            ),
            'executed': event.reason in (0, 6, 8, 9),
            'reason': reasons[event.reason],
        })
    return trades, orders, signals


def materialize_snapshots(result, symbol_data, index, portfolio_id, trades,
                          initial_amount):
    values = np.frombuffer(
        result.snapshot_bytes(), dtype='<f8'
    ).reshape(-1, 4)
    positions = np.frombuffer(result.position_bytes(), dtype='<f8').reshape(
        len(index), len(symbol_data), 6
    )
    symbols = sorted(enumerate(symbol_data), key=lambda item: item[1])
    for trade, price in zip(trades, result.last_prices):
        if price is not None:
            trade.last_reported_price = np.float64(price)
    snapshots = []
    for row_number, (timestamp, row, position_row) in enumerate(
        zip(index, values, positions)
    ):
        cash = (initial_amount if row_number < result.cash_start_row
                else float(row[0]))
        total_value = row[1] if position_row[:, 0].any() else cash
        position_snapshots = []
        for slot, symbol in symbols:
            amount, cost, long_amount, short_amount, long_cost, short_cost = (
                position_row[slot].tolist()
            )
            position_snapshots.append(PositionSnapshot(
                symbol=symbol, amount=amount if amount else 0,
                cost=cost if amount else 0,
                long_amount=long_amount if long_amount else 0,
                short_amount=short_amount if short_amount else 0,
                long_cost=long_cost if long_amount else 0,
                short_cost=short_cost if short_amount else 0,
            ))
        snapshots.append(PortfolioSnapshot(
            portfolio_id=portfolio_id,
            created_at=pd.Timestamp(timestamp).to_pydatetime().replace(
                tzinfo=timezone.utc
            ),
            unallocated=cash, total_value=total_value,
            total_net_gain=float(row[2]), cash_flow=float(row[3]),
            position_snapshots=position_snapshots,
        ))
    return snapshots
