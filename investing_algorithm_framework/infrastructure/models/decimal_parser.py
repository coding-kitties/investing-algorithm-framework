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
