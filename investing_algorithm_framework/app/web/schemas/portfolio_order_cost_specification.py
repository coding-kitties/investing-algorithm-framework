from marshmallow import Schema, fields


class PortfolioOrderCostSpecificationSerializer(Schema):
    portfolio_id = fields.Integer(dump_only=True)
    identifier = fields.String(dump_only=True)
    market = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    fee_percentage = fields.Float(dump_only=True, allow_none=True)
    slippage_percentage = fields.Float(dump_only=True)
    source = fields.String(dump_only=True)
