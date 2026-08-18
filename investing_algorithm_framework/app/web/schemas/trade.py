from marshmallow import Schema, fields


class TradeSerializer(Schema):
    id = fields.Integer(dump_only=True)
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    is_short = fields.Boolean(dump_only=True)
    amount = fields.Float(dump_only=True)
    available_amount = fields.Float(dump_only=True)
    filled_amount = fields.Float(dump_only=True)
    remaining = fields.Float(dump_only=True)
    open_price = fields.Float(dump_only=True)
    cost = fields.Float(dump_only=True)
    net_gain = fields.Float(dump_only=True)
    total_fees = fields.Float(dump_only=True)
    opened_at = fields.DateTime(dump_only=True)
    closed_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
