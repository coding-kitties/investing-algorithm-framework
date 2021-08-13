from marshmallow import Schema, fields


class PositionSerializer(Schema):
    id = fields.Int(dump_only=True)
    symbol = fields.String(dump_only=True)
    amount = fields.Float(dump_only=True)

    # Optional fields
    identifier = fields.Method("get_identifier")
    orders = fields.Method("get_orders")

    @staticmethod
    def get_identifier(obj):
        return obj.portfolio.identifier

    @staticmethod
    def get_orders(obj):
        return obj.orders.count()
