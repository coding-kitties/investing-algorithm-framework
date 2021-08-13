from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_all_tables():
    db.create_all()


def initialize_db(app: Flask):
    db.init_app(app)
    db.app = app

from investing_algorithm_framework.core.models.order_type import OrderType
from investing_algorithm_framework.core.models.order_side import OrderSide
from investing_algorithm_framework.core.models.time_unit import TimeUnit
from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.models.portfolio import Portfolio
from investing_algorithm_framework.core.models.position import Position

__all__ = [
    "db",
    "Portfolio",
    "Position",
    'Order',
    "OrderType",
    'OrderSide',
    "TimeUnit",
    "create_all_tables",
    "initialize_db"
]
