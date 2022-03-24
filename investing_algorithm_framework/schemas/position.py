from marshmallow import Schema, fields


class PositionSerializer(Schema):
    symbol = fields.Method("get_symbol")
    amount = fields.Float(dump_only=True)
    orders = fields.Method("get_orders")

    @staticmethod
    def get_orders(obj):
        return len(obj.get_orders())

    @staticmethod
    def get_symbol(obj):
        return obj.get_symbol()