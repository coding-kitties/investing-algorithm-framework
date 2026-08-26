from marshmallow import Schema, fields


class RunReportSerializer(Schema):
    id = fields.Integer(dump_only=True)
    algorithm_id = fields.String(dump_only=True)
    environment = fields.String(dump_only=True)
    is_paper = fields.Boolean(dump_only=True)
    number_of_iterations = fields.Integer(dump_only=True)
    started_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True)
    orders = fields.Raw(dump_only=True)
    signals = fields.Raw(dump_only=True)
    positions = fields.Raw(dump_only=True)
    portfolios = fields.Raw(dump_only=True)
    trades = fields.Raw(dump_only=True)
    score_cards = fields.Raw(dump_only=True)
