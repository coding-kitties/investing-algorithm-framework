from marshmallow import Schema, fields


class BacktestMetricsSerializer(Schema):
    total_return = fields.Float(dump_only=True)
    sharpe_ratio = fields.Float(dump_only=True)
    calmar_ratio = fields.Float(dump_only=True)
    max_drawdown = fields.Float(dump_only=True)
    cagr = fields.Float(dump_only=True)
    annual_volatility = fields.Float(dump_only=True)
    profit_factor = fields.Float(dump_only=True)
    sortino_ratio = fields.Float(dump_only=True)
    trades_per_year = fields.Float(dump_only=True)
    exposure_ratio = fields.Float(dump_only=True)


class BacktestRunOrderSerializer(Schema):
    reference_id = fields.String(dump_only=True)
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    price = fields.Float(dump_only=True)
    amount = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    order_type = fields.String(dump_only=True)
    order_side = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    filled = fields.Float(dump_only=True)
    remaining = fields.Float(dump_only=True)
    strategy_id = fields.String(dump_only=True)


class BacktestRunTradeSerializer(Schema):
    target_symbol = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    amount = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    opened_at = fields.DateTime(dump_only=True)
    closed_at = fields.DateTime(dump_only=True)
    strategy_id = fields.String(dump_only=True)
    is_short = fields.Boolean(dump_only=True)


class BacktestRunPositionSerializer(Schema):
    symbol = fields.String(dump_only=True)
    amount = fields.Float(dump_only=True)
    cost = fields.Float(dump_only=True)
    gross_amount = fields.Float(dump_only=True)
    net_cost = fields.Float(dump_only=True)
    gross_cost = fields.Float(dump_only=True)
    long_amount = fields.Float(dump_only=True)
    short_amount = fields.Float(dump_only=True)
    long_cost = fields.Float(dump_only=True)
    short_cost = fields.Float(dump_only=True)


class PositionSnapshotSerializer(BacktestRunPositionSerializer):
    portfolio_snapshot_id = fields.String(dump_only=True)


class PortfolioSnapshotSerializer(Schema):
    trading_symbol = fields.String(dump_only=True)
    total_value = fields.Float(dump_only=True)
    cash = fields.Float(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    long_exposure = fields.Float(dump_only=True)
    short_exposure = fields.Float(dump_only=True)
    net_exposure = fields.Float(dump_only=True)
    gross_exposure = fields.Float(dump_only=True)
    position_snapshots = fields.Nested(
        PositionSnapshotSerializer, many=True, dump_only=True
    )


class BacktestRunSerializer(Schema):
    backtest_start_date = fields.DateTime(dump_only=True)
    backtest_end_date = fields.DateTime(dump_only=True)
    backtest_date_range_name = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    initial_unallocated = fields.Float(dump_only=True)
    number_of_runs = fields.Integer(dump_only=True)
    number_of_days = fields.Integer(dump_only=True)
    number_of_trades = fields.Integer(dump_only=True)
    number_of_trades_closed = fields.Integer(dump_only=True)
    number_of_trades_open = fields.Integer(dump_only=True)
    number_of_orders = fields.Integer(dump_only=True)
    number_of_positions = fields.Integer(dump_only=True)
    symbols = fields.List(fields.String(), dump_only=True)
    backtest_metrics = fields.Nested(
        BacktestMetricsSerializer, dump_only=True
    )
    orders = fields.Nested(
        BacktestRunOrderSerializer, many=True, dump_only=True
    )
    trades = fields.Nested(
        BacktestRunTradeSerializer, many=True, dump_only=True
    )
    positions = fields.Nested(
        BacktestRunPositionSerializer, many=True, dump_only=True
    )
    portfolio_snapshots = fields.Nested(
        PortfolioSnapshotSerializer, many=True, dump_only=True
    )


class BacktestResultSerializer(Schema):
    algorithm_id = fields.String(dump_only=True)
    anchor_algorithm_id = fields.String(dump_only=True)
    backtest_id = fields.String(dump_only=True)
    tag = fields.String(dump_only=True)
    parameters = fields.Dict(dump_only=True)
    metadata = fields.Dict(dump_only=True)
    risk_free_rate = fields.Float(dump_only=True)
    strategy_ids = fields.List(fields.String(), dump_only=True)


class BacktestResultSummarySerializer(Schema):
    algorithm_id = fields.String(dump_only=True)
    anchor_algorithm_id = fields.String(dump_only=True)
    tag = fields.String(dump_only=True)
    number_of_vector_runs = fields.Method("get_number_of_vector_runs")
    number_of_event_runs = fields.Method("get_number_of_event_runs")

    @staticmethod
    def get_number_of_vector_runs(obj):
        return len(obj.vector_runs) if obj.vector_runs else 0

    @staticmethod
    def get_number_of_event_runs(obj):
        return len(obj.event_runs) if obj.event_runs else 0
