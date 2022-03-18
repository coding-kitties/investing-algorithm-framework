from .default_order_validator import DefaultOrderValidator
from .order_validator import OrderValidator


class OrderValidatorFactory:

    @staticmethod
    def of(market) -> OrderValidator:
        return DefaultOrderValidator()
