from enum import Enum


class StatelessActions(Enum):
    RUN_STRATEGY = 'RUN_STRATEGY'
    CHECK_PENDING_ORDERS = 'CHECK_PENDING_ORDERS'
    PING = 'PING'
