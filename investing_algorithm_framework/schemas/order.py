from marshmallow import Schema, fields


class OrderSerializer(Schema):
    reference_id = fields.String(dump_only=True)
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    initial_price = fields.Float(dump_only=True)
    price = fields.Float(dump_only=True)
    closing_price = fields.Float(dump_only=True)
    amount_target_symbol = fields.Float(dump_only=True)
    amount_trading_symbol = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    type = fields.String(dump_only=True)
    side = fields.String(dump_only=True)

