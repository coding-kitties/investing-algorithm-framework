"""Persist native transitions before dispatching Python trade hooks."""
from investing_algorithm_framework.domain import OrderSide, PositionMode


def apply_order_transition(native, service, operation, *args, **kwargs):
    previous = args[0] if operation == 'fill' else None
    order = args[1] if previous is not None else args[0]
    previous_fee = (args[1] if len(args) > 1 else
                    kwargs.get('previous_fee', 0)) if operation == 'fee' else 0
    side = OrderSide.from_value(order.order_side).value
    if operation == 'fill' and side == 'SELL':
        service._materialize_mirror_fill_if_needed(order)
    if operation == 'cancel' and side == 'SELL':
        metadata = order.metadata or {}
        if metadata.get('order_reason') in (
                'stop_loss_mirror', 'take_profit_mirror') \
                and not metadata.get('_mirror_allocated'):
            return
    position = service.position_service.get(order.position_id)
    portfolio = service.portfolio_repository.get(position.portfolio_id)
    quote = service.position_service.find({
        'portfolio': portfolio.id, 'symbol': portfolio.trading_symbol,
    })
    price = order.price
    if side in ('BUY', 'SHORT', 'COVER') and not price:
        price = order.reservation_price or 0
    reservation = (order.metadata or {}).get('_reservation_price')
    if reservation is None:
        reservation = order.reservation_price or price
    portfolio_updates, position_updates, quote_updates = \
        native.event_order_transition(
            operation, side,
            [portfolio.unallocated, quote.amount, portfolio.total_cost,
             portfolio.total_trade_volume, position.long_amount,
             position.long_cost, position.short_amount, position.short_cost,
             position.amount],
            [order.amount, order.filled or 0,
             previous.filled if previous is not None else 0,
             price or 0, reservation or 0,
             previous.amount if previous is not None else order.amount,
             order.order_fee or 0, previous_fee or 0,
             order.get_size() if operation == 'create' else 0],
            service._position_mode(portfolio) == PositionMode.HEDGE,
        )
    if position_updates:
        service.position_service.update(position.id, dict(position_updates))
    if portfolio_updates:
        service.portfolio_repository.update(portfolio.id,
                                            dict(portfolio_updates))
    if quote_updates:
        service.position_service.update(quote.id, dict(quote_updates))
    if operation == 'cancel' and side == 'SELL':
        service.trade_service.update_trade_with_removed_sell_order(
            order, position_mode=service._position_mode(portfolio))
    elif operation == 'create' and side == 'SELL' and order.filled > 0:
        service.trade_service.update_trade_with_filled_sell_order(
            order.filled, order)
    elif operation == 'fill':
        difference = order.filled - previous.filled
        if difference <= 0:
            return
        if side == 'BUY':
            trade = service.trade_service.create_trade_at_fill(
                order, difference, price, order.updated_at or order.created_at)
            service._place_mirror_orders_for_trade(trade)
        elif side == 'SHORT':
            service.trade_service.create_short_trade_at_fill(
                order, difference, price, order.updated_at or order.created_at)
        elif side == 'SELL':
            service.trade_service.update_trade_with_filled_sell_order(
                difference, order)
        else:
            service.trade_service.close_short_trade_with_filled_cover_order(
                difference, order)
