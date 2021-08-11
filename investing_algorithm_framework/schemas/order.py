from marshmallow import Schema, fields


class OrderSerializer(Schema):
    id = fields.Int(dump_only=True)
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    price = fields.Float(dump_only=True)
    amount = fields.Float(dump_only=True)
    terminated = fields.Bool(dump_only=True)
    order_type = fields.String(dump_only=True)
    order_side = fields.String(dump_only=True)
    executed = fields.String(dump_only=True)
    successful = fields.String(dump_only=True)

    # Optional fields
    identifier = fields.Method("get_identifier")
    position_id = fields.Int(dump_only=True)

    @staticmethod
    def get_identifier(obj):

        if obj.position is None:
            return None

        return obj.position.portfolio.identifier
