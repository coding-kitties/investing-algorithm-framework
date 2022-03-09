from marshmallow import Schema, fields


# from investing_algorithm_framework.core.performance import PerformanceService


class PortfolioSerializer(Schema):
    identifier = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    unallocated = fields.Float(dump_only=True)
    orders = fields.Method("get_orders")
    positions = fields.Method("get_positions")

    @staticmethod
    def get_orders(obj):
        return obj.get_number_of_orders()

    @staticmethod
    def get_positions(obj):
        return obj.get_number_of_positions()

    # def get_performance(self, obj):
    #     return PerformanceService\
    #         .of_metric(
    #             obj,
    #             PerformanceMetric.OVERALL_PERFORMANCE,
    #             TimeFrame.from_value(
    #                 self.context.get("time_frame", TimeFrame.ONE_DAY.value)
    #             )
    #         )

    # def get_delta(self, obj):
    #     return PerformanceService \
    #         .of_metric(
    #             obj,
    #             PerformanceMetric.DELTA,
    #             TimeFrame.from_value(
    #                 self.context.get("time_frame", TimeFrame.ONE_DAY.value)
    #             )
    #         )
