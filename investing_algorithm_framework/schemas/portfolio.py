from marshmallow import Schema, fields
from investing_algorithm_framework.core.models import Position, Order


class PortfolioSerializer(Schema):
    id = fields.Integer(dump_only=True)
    identifier = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    unallocated = fields.Float(dump_only=True)
    delta = fields.Float(dump_only=True)
    allocated = fields.Float(dump_only=True)
    allocated_percentage = fields.Float(dump_only=True)
    unallocated_percentage = fields.Float(dump_only=True)
    realized = fields.Float(dump_only=True)
    market = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    orders = fields.Method("get_orders")
    positions = fields.Method("get_positions")

    @staticmethod
    def get_orders(obj):
        positions = obj.positions.with_entities(Position.id)

        # Retrieve orders
        query_set = Order.query \
            .filter(Order.position_id.in_(positions))

        return query_set.count()

    @staticmethod
    def get_positions(obj):
        return obj.positions.count()
