from marshmallow import Schema, fields


class PortfolioOrderCostSerializer(Schema):
    portfolio_id = fields.Integer(dump_only=True)
    identifier = fields.String(dump_only=True)
    market = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    number_of_orders = fields.Integer(dump_only=True)
    number_of_filled_orders = fields.Integer(dump_only=True)
    total_order_fee = fields.Float(dump_only=True)
    total_slippage = fields.Float(dump_only=True)
