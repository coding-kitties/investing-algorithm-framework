from unittest import TestCase
from investing_algorithm_framework.indicators import is_divergence

import pandas as pd

class TestDetectBearishSequences(TestCase):

    def test_detect_bearish_sequence(self):
        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, 0, 0, 0, 0, -1, 0, 0],
            "Close_highs": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertFalse(is_divergence(df, window_size=2, number_of_data_points=2, column_one="RSI_highs", column_two="Close_highs"))
        self.assertTrue(is_divergence(df, window_size=2, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, 0, 0, 0, 0, -1, 0, 0],
            "Close_highs": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)
        self.assertFalse(is_divergence(df, window_size=10, number_of_data_points=1, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 1, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 0, -1, 0, 0, 0, 0, 0, 0, 1],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)

        self.assertFalse(is_divergence(df, window_size=6, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))
        self.assertTrue(is_divergence(df, window_size=7, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [-1.0],
            "Close_highs": [1.0],
            "DateTime": pd.date_range("2021-01-01", periods=1, freq="D")
        })

        # Set index to DateTime 
        df.set_index("DateTime", inplace=True)

        self.assertTrue(is_divergence(df, window_size=1, number_of_data_points=1, column_one="RSI_highs", column_two="Close_highs")) 
       
    def test_detect_bearish_sequence_with_wrong_params(self):

        df = pd.DataFrame({
            "RSI_highs": [0, 1, 0, -1, 0, 0, 0, 0, -1, 0],
            "Close_highs": [0, 0, -1, 0, 0, 0, 0, 1, 0, 1],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })

        # Set index to DateTime
        df.set_index("DateTime", inplace=True)
        self.assertTrue(is_divergence(df, window_size=8, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))
        self.assertFalse(is_divergence(df, window_size=8, number_of_data_points=1, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 1, -1, 0, 0, 0, 0, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })
        self.assertFalse(is_divergence(df, window_size=6, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })
        self.assertFalse(is_divergence(df, window_size=6, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })
        self.assertTrue(is_divergence(df, window_size=6, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })
        self.assertTrue(is_divergence(df, window_size=1, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))

        df = pd.DataFrame({
            "RSI_highs": [0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
            "Close_highs": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            "DateTime": pd.date_range("2021-01-01", periods=10, freq="D")
        })
        self.assertFalse(is_divergence(df, window_size=1, number_of_data_points=10, column_one="RSI_highs", column_two="Close_highs"))
