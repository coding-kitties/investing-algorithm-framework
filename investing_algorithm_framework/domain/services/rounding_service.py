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
            d = decimal.Decimal(value)
            ctx.rounding = decimal.ROUND_DOWN
            return float(round(d, amount_of_decimals))

    @staticmethod
    def count_decimals(number):
        decimal_str = str(number)
        if '.' in decimal_str:
            return len(decimal_str.split('.')[1])
        else:
            return 0
