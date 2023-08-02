from marshmallow import Schema, fields

from investing_algorithm_framework.dependency_container \
    import DependencyContainer


class PortfolioSerializer(Schema):
    identifier = fields.String(dump_only=True)
    trading_symbol = fields.String(dump_only=True)
    unallocated = fields.Float(dump_only=True)
    orders = fields.Method("get_orders")
    positions = fields.Method("get_positions")

    @staticmethod
    def get_orders(obj):
        order_service = DependencyContainer.order_service()
        return order_service.count({"portfolio": obj.identifier})

    @staticmethod
    def get_positions(obj):
        position_service = DependencyContainer.position_service()
        return position_service.count({"portfolio": obj.id})
