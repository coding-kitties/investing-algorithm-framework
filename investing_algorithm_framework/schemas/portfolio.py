from marshmallow import Schema, fields
from investing_algorithm_framework.core.models import Position, Order, \
    PerformanceMetric, TimeFrame
from investing_algorithm_framework.core.performance import PerformanceService


class PortfolioSerializer(Schema):
    id = fields.Integer(dump_only=True)
    identifier = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    unallocated = fields.Float(dump_only=True)
    allocated = fields.Float(dump_only=True)
    allocated_percentage = fields.Float(dump_only=True)
    unallocated_percentage = fields.Float(dump_only=True)
    realized = fields.Float(dump_only=True)
    market = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    orders = fields.Method("get_orders")
    positions = fields.Method("get_positions")
    performance = fields.Method("get_performance")
    delta = fields.Method("get_delta")

    @staticmethod
    def get_orders(obj):
        positions = obj.positions.with_entities(Position.id)

        # Retrieve orders
        query_set = Order.query \
            .filter(Order.position_id.in_(positions))

        return query_set.count()

    @staticmethod
    def get_positions(obj):
        return obj.positions.count()

    def get_performance(self, obj):
        return PerformanceService\
            .of_metric(
                obj,
                PerformanceMetric.OVERALL_PERFORMANCE,
                TimeFrame.from_value(
                    self.context.get("time_frame", TimeFrame.ONE_DAY.value)
                )
            )

    def get_delta(self, obj):
        return PerformanceService \
            .of_metric(
                obj,
                PerformanceMetric.DELTA,
                TimeFrame.from_value(
                    self.context.get("time_frame", TimeFrame.ONE_DAY.value)
                )
            )
