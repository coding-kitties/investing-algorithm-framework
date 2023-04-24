from marshmallow import Schema, fields
from investing_algorithm_framework.dependency_container import \
    DependencyContainer


class PositionSerializer(Schema):
    symbol = fields.String()
    amount = fields.Float(dump_only=True)
    orders = fields.Method("get_orders")

    @staticmethod
    def get_orders(obj):
        order_service = DependencyContainer.order_service()
        return order_service.count({"position": obj.id})
