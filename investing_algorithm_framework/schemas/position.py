from marshmallow import Schema, fields


class PositionSerializer(Schema):
    id = fields.Int(dump_only=True)
    symbol = fields.String(dump_only=True)
    amount = fields.Float(dump_only=True)

    # Optional fields
    broker = fields.Method("get_broker")
    orders = fields.Method("get_orders")

    @staticmethod
    def get_broker(obj):
        return obj.portfolio.broker

    @staticmethod
    def get_orders(obj):
        return obj.orders.count()
