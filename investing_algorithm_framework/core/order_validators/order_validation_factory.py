from .order_validator import OrderValidator
from .default_order_validator import DefaultOrderValidator


class OrderValidatorFactory:

    @staticmethod
    def of(market) -> OrderValidator:
        return DefaultOrderValidator()
