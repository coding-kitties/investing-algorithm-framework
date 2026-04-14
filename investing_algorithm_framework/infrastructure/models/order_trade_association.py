from sqlalchemy import Table, Column, BigInteger, ForeignKey
from investing_algorithm_framework.infrastructure.database import SQLBaseModel

# Association table
order_trade_association = Table(
    'order_trade',  # Table name
    SQLBaseModel.metadata,
    Column('order_id', BigInteger, ForeignKey('orders.id'), primary_key=True),
    Column('trade_id', BigInteger, ForeignKey('trades.id'), primary_key=True)
)
