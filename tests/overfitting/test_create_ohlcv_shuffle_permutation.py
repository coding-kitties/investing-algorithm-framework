import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
from investing_algorithm_framework import create_ohlcv_shuffle_permutation


class TestCreateOHLCVShufflePermutation(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'Datetime': pd.date_range('2023-01-01', periods=5, freq='D'),
            'Open': [1, 2, 3, 4, 5],
            'High': [2, 3, 4, 5, 6],
            'Low': [0, 1, 2, 3, 4],
            'Close': [1.5, 2.5, 3.5, 4.5, 5.5],
            'Volume': [10, 20, 30, 40, 50]
        })

    def test_shape_and_columns(self):
        shuffled = create_ohlcv_shuffle_permutation(self.df)
        self.assertEqual(shuffled.shape, self.df.shape)
        self.assertListEqual(list(shuffled.columns), list(self.df.columns))

    def test_Datetime_unchanged(self):
        shuffled = create_ohlcv_shuffle_permutation(self.df)
        pd.testing.assert_series_equal(shuffled['Datetime'], self.df['Datetime'])

    def test_rows_are_permuted(self):
        # Run multiple times to reduce chance of accidental same order
        orders = []
        for _ in range(5):
            shuffled = create_ohlcv_shuffle_permutation(self.df)
            orders.append(tuple(shuffled.drop(columns='Datetime').values.flatten()))
        # At least one shuffle should differ from the original
        original = tuple(self.df.drop(columns='Datetime').values.flatten())
        self.assertTrue(any(order != original for order in orders))

    def test_all_rows_present(self):
        shuffled = create_ohlcv_shuffle_permutation(self.df)
        # Compare sorted values (excluding Datetime)
        orig_sorted = self.df.drop(columns='Datetime').sort_values(by=list(self.df.columns[1:])).reset_index(drop=True)
        shuf_sorted = shuffled.drop(columns='Datetime').sort_values(by=list(self.df.columns[1:])).reset_index(drop=True)
        assert_frame_equal(orig_sorted, shuf_sorted)

    def test_input_not_modified(self):
        df_copy = self.df.copy(deep=True)
        _ = create_ohlcv_shuffle_permutation(self.df)
        assert_frame_equal(self.df, df_copy)