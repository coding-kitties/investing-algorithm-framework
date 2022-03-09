from marshmallow import Schema, fields


class PositionSerializer(Schema):
    symbol = fields.String(dump_only=True)
    amount = fields.Float(dump_only=True)
    orders = fields.Method("get_orders")

    @staticmethod
    def get_orders(obj):
        return len(obj.get_orders())
