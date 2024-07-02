from decimal import Decimal
from unittest import TestCase

from investing_algorithm_framework.domain import \
    parse_string_to_decimal, parse_decimal_to_string


class Test(TestCase):

    def test_decimal_to_string(self):
        # Create a string value of a decimal
        decimal_value = Decimal('97.17312522036036245646')
        string_value = parse_decimal_to_string(decimal_value)
        self.assertEqual(string_value, '97.17312522036036245646')

    def test_string_to_decimal(self):
        parse_string_to_decimal('97.17312522036036245646')
        parse_string_to_decimal('2004.5303357979318')
