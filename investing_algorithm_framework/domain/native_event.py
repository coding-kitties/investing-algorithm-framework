"""Run-local native event transitions; no resident execution history."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


_engine = ContextVar('native_event_accounting', default=None)


def load_native_event_accounting():
    import iaf_confluence_native as native

    if getattr(native, 'EVENT_ACCOUNTING_SEMANTICS_VERSION', None) != \
            'event-accounting-v1':
        raise ValueError('Native event accounting version mismatch')
    if getattr(native, 'EVENT_SETTLEMENT_SEMANTICS_VERSION', None) != \
            'event-settlement-v1':
        raise ValueError('Native event settlement version mismatch')
    if getattr(native, 'EVENT_LIFECYCLE_SEMANTICS_VERSION', None) != \
            'event-lifecycle-v1':
        raise ValueError('Native event lifecycle version mismatch')
    for name, version in (
        ('EVENT_ARCHIVE_SEMANTICS_VERSION', 'event-archive-v2'),
        ('EVENT_FILL_SEMANTICS_VERSION', 'event-fill-v1'),
        ('EVENT_SCHEDULE_SEMANTICS_VERSION', 'event-schedule-v1'),
    ):
        if getattr(native, name, None) != version:
            raise ValueError(f'Native event capability mismatch: {name}')
    return native


def native_event_engine():
    return _engine.get()


@contextmanager
def native_event_scope(backend):
    if backend not in ('python', 'rust'):
        raise ValueError('Accounting backend must be python or rust')
    native = load_native_event_accounting() if backend == 'rust' else None
    token = _engine.set(native)
    try:
        yield native
    finally:
        _engine.reset(token)


def native_order(operation):
    def decorate(method):
        @wraps(method)
        def dispatch(service, *args, **kwargs):
            native = _engine.get()
            if native is None:
                return method(service, *args, **kwargs)
            from investing_algorithm_framework.services.native_accounting \
                import apply_order_transition
            return apply_order_transition(
                native, service, operation, *args, **kwargs)
        return dispatch
    return decorate


def native_risk(*, stop, check):
    def decorate(method):
        @wraps(method)
        def dispatch(rule, current_price=None, date=None):
            native = _engine.get()
            if native is None:
                return (method(rule, current_price) if check
                        else method(rule, current_price, date))
            if check and current_price is None:
                return False
            key = 'stop_loss_price' if stop else 'take_profit_price'
            triggered, watermark, threshold, dated = \
                native.event_risk_transition(
                    stop, bool(rule.trailing), bool(rule.is_short),
                    bool(rule.active), rule.sold_amount, rule.sell_amount,
                    rule.open_price, rule.percentage, current_price,
                    rule.high_water_mark, getattr(rule, key), check,
                )
            if watermark != rule.high_water_mark:
                rule.high_water_mark = current_price
            if threshold != getattr(rule, key):
                setattr(rule, key, threshold)
            if dated:
                rule.high_water_mark_date = date
            return triggered if check else None
        return dispatch
    return decorate
