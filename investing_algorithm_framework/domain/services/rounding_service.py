import decimal


class RoundingService:
    """
    Service to round numbers to a certain amount of decimals.
    It will always round down.
    """

    @staticmethod
    def round_down(value, amount_of_decimals):

        if RoundingService.count_decimals(value) <= amount_of_decimals:
            return value

        with decimal.localcontext() as ctx:
            d = decimal.Decimal(str(value))
            ctx.rounding = decimal.ROUND_DOWN
            return float(round(d, amount_of_decimals))

    @staticmethod
    def count_decimals(number):
        value = decimal.Decimal(str(number))
        if not value.is_finite():
            return 0
        return max(0, -value.as_tuple().exponent)
