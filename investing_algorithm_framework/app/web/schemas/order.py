from marshmallow import Schema, fields


class OrderSerializer(Schema):
    reference_id = fields.String(dump_only=True)
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    price = fields.Float(dump_only=True)
    amount = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    order_type = fields.String(dump_only=True)
    order_side = fields.String(dump_only=True)
