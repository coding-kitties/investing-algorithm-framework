import unittest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal
from investing_algorithm_framework import create_ohlcv_shuffle_returns_and_reconstruct_permutation

class TestCreateOHLCVShuffleReturnsAndReconstructPermutation(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'Datetime': pd.date_range('2023-01-01', periods=6, freq='D'),
            'Open': [1, 2, 3, 4, 5, 6],
            'High': [2, 3, 4, 5, 6, 7],
            'Low': [0, 1, 2, 3, 4, 5],
            'Close': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
            'Volume': [10, 20, 30, 40, 50, 60]
        })

    def test_shape_and_columns(self):
        shuffled = create_ohlcv_shuffle_returns_and_reconstruct_permutation(self.df)
        # Should have one less row due to pct_change and same columns except 'return'
        expected_columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
        self.assertEqual(list(shuffled.columns), expected_columns)
        self.assertEqual(shuffled.shape[0], self.df.shape[0] - 1)

    def test_timestamp_unchanged(self):
        shuffled = create_ohlcv_shuffle_returns_and_reconstruct_permutation(self.df)
        pd.testing.assert_series_equal(shuffled['Datetime'], self.df['Datetime'][1:], check_names=False)

    def test_close_reconstruction(self):
        # The first close should match the original second close if returns are not shuffled
        df_copy = self.df.copy()
        df_copy['return'] = df_copy['Close'].pct_change()
        # No shuffle: use original returns
        price_start = df_copy['Close'].iloc[0]
        orig_returns = df_copy['return'].dropna().values
        reconstructed_prices = [price_start]
        for r in orig_returns:
            reconstructed_prices.append(reconstructed_prices[-1] * (1 + r))
        # Now shuffle with a fixed seed to get deterministic output
        np.random.seed(42)
        shuffled = create_ohlcv_shuffle_returns_and_reconstruct_permutation(self.df)
        # The reconstructed prices should not match the original closes (since shuffled)
        self.assertFalse(np.allclose(shuffled['Close'].values, self.df['Close'].values[1:]))

    def test_input_not_modified(self):
        df_copy = self.df.copy(deep=True)
        _ = create_ohlcv_shuffle_returns_and_reconstruct_permutation(self.df)
        assert_frame_equal(self.df, df_copy)

    def test_no_return_column(self):
        shuffled = create_ohlcv_shuffle_returns_and_reconstruct_permutation(self.df)
        self.assertNotIn('return', shuffled.columns)