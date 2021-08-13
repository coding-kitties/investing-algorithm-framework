from .order_validator import OrderValidator


class DefaultOrderValidator(OrderValidator):

    def _validate_order(self, order, portfolio):
        pass
