from decimal import Decimal, getcontext


def count_number_of_decimals(value) -> int:
    value = str(value)
    if "." in value:
        return len(value) - value.index(".") - 1
    else:
        return 0


def parse_decimal(value) -> Decimal:
    getcontext().prec = count_number_of_decimals(value)
    return Decimal(value)


def parse_decimal_to_string(decimal, precision=None):

    if decimal is None:
        return None

    if isinstance(decimal, str):
        return decimal

    value_str = str(Decimal(decimal))

    if precision is None:
        return value_str

    value_decimal = Decimal(value_str)
    value_with_precision = format(value_decimal, f'.{precision}f')
    return value_with_precision


def parse_string_to_decimal(value):

    if value is None:
        return None

    return Decimal(value)
