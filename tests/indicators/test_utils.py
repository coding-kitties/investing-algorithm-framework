from unittest import TestCase
from investing_algorithm_framework.indicators import is_crossover, \
    has_any_higher_then_threshold, has_values_above_threshold, \
    get_slope, has_slope_above_threshold, has_values_below_threshold
import pandas as pd

class TestUtils(TestCase):

    def test_crossover(self):
        df = pd.DataFrame({
            "EMA_50": [200, 201, 202, 203, 204, 205, 206, 208, 208, 210],
            "EMA_200": [200, 201, 202, 203, 204, 205, 206, 207, 209, 209],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertTrue(is_crossover(df, first_column="EMA_50", second_column="EMA_200"))
        self.assertTrue(is_crossover(df, first_column="EMA_50", second_column="EMA_200", number_of_data_points=3))

        df = pd.DataFrame({
            "EMA_50": [200, 201, 202, 203, 204, 205, 206, 208, 210, 210],
            "EMA_200": [200, 201, 202, 203, 204, 205, 206, 209, 209, 209],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertFalse(is_crossover(df, first_column="EMA_50", second_column="EMA_200"))
        self.assertTrue(is_crossover(df, first_column="EMA_50", second_column="EMA_200", number_of_data_points=3))

    def test_has_any_higher_then_threshold(self):
        df = pd.DataFrame({
            "RSI": [70, 71, 72, 73, 74, 75, 76, 77, 78, 79],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertTrue(has_any_higher_then_threshold(df, column="RSI", threshold=70, number_of_data_points=10, strict=False))
        self.assertFalse(has_any_higher_then_threshold(df, column="RSI", threshold=80, number_of_data_points=10, strict=False))
        self.assertTrue(has_any_higher_then_threshold(df, column="RSI", threshold=70, number_of_data_points=10, strict=True))
        self.assertFalse(has_any_higher_then_threshold(df, column="RSI", threshold=80, number_of_data_points=10, strict=True))

        df = pd.DataFrame({
            "RSI": [70, 71, 100, 73, 20, 75, 15, 77, 78, 79],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertTrue(has_any_higher_then_threshold(df, column="RSI", threshold=100, strict=False, number_of_data_points=10))
        self.assertFalse(has_any_higher_then_threshold(df, column="RSI", threshold=100, strict=True, number_of_data_points=10))
        self.assertFalse(has_any_higher_then_threshold(df, column="RSI", threshold=79, strict=True))
        self.assertTrue(has_any_higher_then_threshold(df, column="RSI", threshold=78, strict=True))
        self.assertTrue(has_any_higher_then_threshold(df, column="RSI", threshold=79, strict=False))
        self.assertFalse(has_any_higher_then_threshold(df, column="RSI", threshold=80, strict=True))

    def test_get_slope(self):
        df = pd.DataFrame({
            "RSI": [2, 5, 6, 5, 4, 7, 7, 8, 9, 7, 5],
            "DateTime": pd.date_range("2021-01-01", periods=11, freq="D")
        })
        slope = get_slope(df, column="RSI", number_of_data_points=2)
        self.assertAlmostEqual(slope, -2)

        slope = get_slope(df, column="RSI", number_of_data_points=3)
        self.assertAlmostEqual(slope, -2)

        slope = get_slope(df, column="RSI", number_of_data_points=4)
        self.assertAlmostEqual(slope, -1.1)

    def test_has_slope_above_threshold(self):
        df = pd.DataFrame({
            "RSI": [2, 5, 6, 5, 4, 9, 7, 6, 9, 7, 5],
            "DateTime": pd.date_range("2021-01-01", periods=11, freq="D")
        })
        self.assertTrue(
            has_slope_above_threshold(
                df, column="RSI", threshold=-0.4, number_of_data_points=5, window_size=5
            )
        )
        self.assertTrue(
            has_slope_above_threshold(
                df, column="RSI", threshold=0.2, number_of_data_points=5, window_size=4
            )
        )
        df = pd.DataFrame({
            "RSI": [2, 5],
            "DateTime": pd.date_range("2021-01-01", periods=2, freq="D")
        })
        self.assertTrue(
            has_slope_above_threshold(
                df, column="RSI", threshold=2, number_of_data_points=2, window_size=2
            )
        )

    def test_has_values_above_threshold(self):
        df = pd.DataFrame({
            "RSI": [2, 5, 6, 5, 10, 9, 7, 7, 9, 7, 5],
            "DateTime": pd.date_range("2021-01-01", periods=11, freq="D")
        })
        self.assertTrue(
            has_values_above_threshold(
                df,
                column="RSI",
                threshold=1,
                number_of_data_points=5,
                proportion=100
            )
        )
        self.assertFalse(
            has_values_above_threshold(
                df,
                column="RSI",
                threshold=7,
                number_of_data_points=5,
                proportion=100
            )
        )
        self.assertTrue(
            has_values_above_threshold(
                df,
                column="RSI",
                threshold=6,
                number_of_data_points=6,
                proportion=100,
                window_size=5
            )
        )
        self.assertTrue(
            has_values_above_threshold(
                df,
                column="RSI",
                threshold=9,
                number_of_data_points=10,
                proportion=20,
                window_size=5
            )
        )
        self.assertFalse(
            has_values_above_threshold(
                df,
                column="RSI",
                threshold=9,
                number_of_data_points=10,
                proportion=40,
                window_size=5
            )
        )

    def test_has_values_below_threshold(self):
        df = pd.DataFrame({
            "RSI": [2, 5, 6, 5, 10, 8, 7, 7, 5, 7, 9],
            "DateTime": pd.date_range("2021-01-01", periods=11, freq="D")
        })
        self.assertTrue(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=8,
                number_of_data_points=5,
                proportion=80
            )
        )
        self.assertFalse(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=8,
                number_of_data_points=5,
                proportion=90
            )
        )
        self.assertTrue(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=10,
                number_of_data_points=5,
                proportion=100
            )
        )
        self.assertFalse(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=4,
                number_of_data_points=5,
                proportion=100
            )
        )
        self.assertFalse(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=8,
                number_of_data_points=6,
                proportion=100,
                window_size=5
            )
        )
        self.assertTrue(
            has_values_below_threshold(
                df,
                column="RSI",
                threshold=9,
                number_of_data_points=6,
                proportion=100,
                window_size=5
            )
        )
