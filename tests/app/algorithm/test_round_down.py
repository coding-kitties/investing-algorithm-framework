from unittest import TestCase

from investing_algorithm_framework.domain import RoundingService


class Test(TestCase):

    def count_decimals(self, number):
        decimal_str = str(number)
        if '.' in decimal_str:
            return len(decimal_str.split('.')[1])
        else:
            return 0

    def test_round_down(self):
        new_value = RoundingService.round_down(1, 3)
        self.assertEqual(
            0, self.count_decimals(new_value)
        )
        self.assertEqual(1, new_value)
        new_value = RoundingService.round_down(1.23456789, 2)
        self.assertEqual(
            2, self.count_decimals(new_value)
        )
        self.assertEqual(1.23, new_value)
        new_value = RoundingService.round_down(1.987654321, 3)
        self.assertEqual(
            3, self.count_decimals(new_value)
        )
        self.assertEqual(1.987, new_value)
        new_value = RoundingService.round_down(1.987654321, 4)
        self.assertEqual(
            4, self.count_decimals(new_value)
        )
        self.assertEqual(1.9876, new_value)
        new_value = RoundingService.round_down(1.987654321, 5)
        self.assertEqual(
            5, self.count_decimals(new_value)
        )
        self.assertEqual(1.98765, new_value)
        new_value = RoundingService.round_down(1.987654321, 6)
        self.assertEqual(
            6, self.count_decimals(new_value)
        )
        self.assertEqual(1.987654, new_value)
        new_value = RoundingService.round_down(1.987654321, 7)
        self.assertEqual(
            7, self.count_decimals(new_value)
        )
        self.assertEqual(1.9876543, new_value)
        new_value = RoundingService.round_down(1.987654321, 8)
        self.assertEqual(
            8, self.count_decimals(new_value)
        )
        self.assertEqual(1.98765432, new_value)
        new_value = RoundingService.round_down(1.987654321, 9)
        self.assertEqual(
            9, self.count_decimals(new_value)
        )
        self.assertEqual(1.987654321, new_value)
        new_value = RoundingService.round_down(1.987654321, 10)
        self.assertEqual(
            9, self.count_decimals(new_value)
        )
        self.assertEqual(1.987654321, new_value)

    def test_round_down_scientific_notation(self):
        for value, decimals, expected in [
            (1e-7, 6, 0.0),
            (1.234e-7, 8, 1.2e-7),
            (1.234e-7, 9, 1.23e-7),
            (-1.234e-7, 8, -1.2e-7),
            (1e-7, 7, 1e-7),
            (1.234e-7, 10, 1.234e-7),
        ]:
            with self.subTest(value=value, decimals=decimals):
                self.assertEqual(
                    RoundingService.round_down(value, decimals), expected
                )

    def test_count_decimals_scientific_notation(self):
        for value, expected in [
            (1e-7, 7), (1.234e-7, 10), (-1.234e-7, 10),
            (1e20, 0), (1.23e20, 0), (1.23, 2), (1, 0),
        ]:
            with self.subTest(value=value):
                self.assertEqual(
                    RoundingService.count_decimals(value), expected
                )
