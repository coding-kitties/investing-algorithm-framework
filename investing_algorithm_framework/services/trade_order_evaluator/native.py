"""Optional pure native candle selection; Python retains fill side effects."""
from datetime import datetime, timezone
import math

import polars as pl

from investing_algorithm_framework.domain import OrderSide, OrderType


class NativeEventFillUnsupported(ValueError):
    """The native selector cannot preserve this input's Python semantics."""


def load_native_event_fills():
    import iaf_confluence_native as native

    version = getattr(native, 'EVENT_FILL_SEMANTICS_VERSION', None)
    if version != 'event-fill-v1':
        raise NativeEventFillUnsupported('Native event fill version mismatch')
    return native


def select_native_fill(native, order, frame):
    kinds = (OrderType.MARKET, OrderType.LIMIT,
             OrderType.STOP, OrderType.STOP_LIMIT)
    kind = next((index for index, value in enumerate(kinds)
                 if value.equals(order.order_type)), None)
    buy = (OrderSide.BUY.equals(order.order_side)
           or OrderSide.COVER.equals(order.order_side))
    sell = (OrderSide.SELL.equals(order.order_side)
            or OrderSide.SHORT.equals(order.order_side))
    if kind is None or not (buy or sell):
        raise NativeEventFillUnsupported('Unsupported order type or side')
    if not {'Datetime', 'Open', 'Low', 'High'}.issubset(frame.columns):
        raise NativeEventFillUnsupported('Missing native candle columns')
    dtype = frame.schema['Datetime']
    updated = order.updated_at
    if (not isinstance(dtype, pl.Datetime)
            or type(updated) is not datetime
            or (dtype.time_zone is None) != (updated.tzinfo is None)):
        raise NativeEventFillUnsupported(
            f'Unsupported timestamp types: {dtype}, {type(updated).__name__}'
        )
    if updated.tzinfo is not None:
        updated = updated.astimezone(timezone.utc).replace(tzinfo=None)
    delta = updated - datetime(1970, 1, 1)
    updated_us = ((delta.days * 86400 + delta.seconds) * 1000000
                  + delta.microseconds)
    times = frame['Datetime'].dt.epoch('us').to_list()
    if any(value is None for value in times):
        raise NativeEventFillUnsupported('Null candle timestamps')
    lows, highs = frame['Low'].to_list(), frame['High'].to_list()
    price = order.price if kind != 0 else 0.0
    stop = order.get_stop_price() if kind >= 2 else None
    numbers = lows + highs + frame['Open'].to_list() + [price]
    if stop is not None:
        numbers.append(stop)
    if any(type(value) not in (int, float)
           or (type(value) is int and abs(value) > 2 ** 53)
           or not math.isfinite(value) for value in numbers):
        raise NativeEventFillUnsupported('Native fills require finite numbers')
    return native.event_fill_decision(
        times, lows, highs, updated_us, kind, buy, price, stop,
        bool(order.is_triggered()),
    )
