import unittest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal
from investing_algorithm_framework import create_ohlcv_shuffle_block_permutation


class TestCreateOHLCVShuffleBlockPermutation(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'Datetime': pd.date_range('2023-01-01', periods=12, freq='D'),
            'open': np.arange(1, 13),
            'high': np.arange(2, 14),
            'low': np.arange(0, 12),
            'close': np.arange(1.5, 13.5),
            'volume': np.arange(10, 22)
        })

    def test_shape_and_columns(self):
        shuffled = create_ohlcv_shuffle_block_permutation(self.df, block_size=4)
        self.assertEqual(shuffled.shape, self.df.shape)
        self.assertListEqual(list(shuffled.columns), list(self.df.columns))

    def test_Datetime_unchanged(self):
        shuffled = create_ohlcv_shuffle_block_permutation(self.df, block_size=4)
        pd.testing.assert_series_equal(shuffled['Datetime'], self.df['Datetime'])

    def test_all_rows_present(self):
        shuffled = create_ohlcv_shuffle_block_permutation(self.df, block_size=4)
        orig_sorted = self.df.drop(columns='Datetime').sort_values(by=list(self.df.columns[1:])).reset_index(drop=True)
        shuf_sorted = shuffled.drop(columns='Datetime').sort_values(by=list(self.df.columns[1:])).reset_index(drop=True)
        assert_frame_equal(orig_sorted, shuf_sorted)

    def test_input_not_modified(self):
        df_copy = self.df.copy(deep=True)
        _ = create_ohlcv_shuffle_block_permutation(self.df, block_size=4)
        assert_frame_equal(self.df, df_copy)
