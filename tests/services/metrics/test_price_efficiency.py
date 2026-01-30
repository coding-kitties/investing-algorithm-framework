from unittest import TestCase
from datetime import datetime, timedelta
import pandas as pd

from investing_algorithm_framework import get_price_efficiency_ratio
from investing_algorithm_framework.domain.exceptions import OperationalException


class TestGetPriceEfficiencyRatio(TestCase):

    def _create_dataframe(self, prices, start_date=None):
        """
        Helper to create a DataFrame with Close prices and datetime index.

        Args:
            prices: List of close prices
            start_date: Start datetime (default: 2021-01-01)

        Returns:
            DataFrame with datetime index and Close column
        """
        if start_date is None:
            start_date = datetime(2021, 1, 1)

        dates = [start_date + timedelta(days=i) for i in range(len(prices))]
        df = pd.DataFrame({'Close': prices}, index=pd.DatetimeIndex(dates))
        return df

    # ==========================================================
    # Basic Functionality Tests
    # ==========================================================

    def test_get_price_efficiency_ratio_volatile(self):
        """Test price efficiency ratio with volatile price movement."""
        # Given: Large swings between prices
        data = {
            'DateTime': [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5)
            ],
            'Close': [100, 102, 90, 105, 110]
        }
        df = pd.DataFrame(data)
        df.set_index('DateTime', inplace=True)

        # When
        result = get_price_efficiency_ratio(df)

        # Then: Low efficiency due to volatile path
        # Net change = |110 - 100| = 10
        # Sum of abs changes = |2| + |-12| + |15| + |5| = 34
        # Efficiency = 10 / 34 ≈ 0.294
        self.assertAlmostEqual(result, 0.294, delta=0.01)

    def test_get_price_efficiency_ratio_smooth(self):
        """Test price efficiency ratio with smooth price movement."""
        # Given: Relatively smooth upward trend
        data = {
            'DateTime': [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5)
            ],
            'Close': [100, 102, 101, 105, 110]
        }
        df = pd.DataFrame(data)
        df.set_index('DateTime', inplace=True)

        # When
        result = get_price_efficiency_ratio(df)

        # Then: Higher efficiency due to smoother path
        # Net change = |110 - 100| = 10
        # Sum of abs changes = |2| + |-1| + |4| + |5| = 12
        # Efficiency = 10 / 12 ≈ 0.833
        self.assertAlmostEqual(result, 0.833, delta=0.01)

    def test_perfect_efficiency_straight_up(self):
        """
        Test price efficiency ratio with perfectly efficient upward movement.
        When price only moves in one direction, efficiency should be 1.0.
        """
        prices = [100, 102, 105, 108, 110]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = 10, Sum of changes = 2 + 3 + 3 + 2 = 10
        # Efficiency = 10 / 10 = 1.0
        self.assertAlmostEqual(result, 1.0, delta=0.01)

    def test_perfect_efficiency_straight_down(self):
        """
        Test price efficiency ratio with perfectly efficient downward movement.
        When price only moves in one direction, efficiency should be 1.0.
        """
        prices = [110, 108, 105, 102, 100]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = |100 - 110| = 10
        # Sum of changes = |-2| + |-3| + |-3| + |-2| = 10
        # Efficiency = 10 / 10 = 1.0
        self.assertAlmostEqual(result, 1.0, delta=0.01)

    def test_low_efficiency_round_trip(self):
        """
        Test price efficiency ratio when price returns to starting point.
        Net change is zero, so efficiency should be 0.
        """
        prices = [100, 120, 100]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = |100 - 100| = 0
        # Sum of changes = |20| + |-20| = 40
        # Efficiency = 0 / 40 = 0.0
        self.assertEqual(result, 0.0)

    def test_very_low_efficiency_oscillating(self):
        """Test with highly oscillating prices (very inefficient)."""
        # Price swings back and forth but ends near start
        prices = [100, 110, 95, 105, 90, 100, 102]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = |102 - 100| = 2
        # Sum of abs changes is much larger
        # Should have low efficiency
        self.assertLess(result, 0.1)

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_two_data_points(self):
        """Test with minimum viable data (two points)."""
        prices = [100, 110]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = 10, Sum of changes = 10
        # Efficiency = 1.0 (perfect efficiency with only 2 points)
        self.assertAlmostEqual(result, 1.0, delta=0.01)

    def test_constant_price(self):
        """Test when price doesn't change at all."""
        prices = [100, 100, 100, 100, 100]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = 0, Sum of changes = 0
        # This will cause division by zero - check behavior
        # Should return NaN or handle gracefully
        self.assertTrue(pd.isna(result) or result == 0.0)

    def test_single_large_move(self):
        """Test with one large move followed by flat period."""
        prices = [100, 150, 150, 150, 150]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Net change = 50, Sum of changes = 50 + 0 + 0 + 0 = 50
        # Efficiency = 1.0
        self.assertAlmostEqual(result, 1.0, delta=0.01)

    def test_small_price_values(self):
        """Test with very small price values."""
        prices = [0.001, 0.0012, 0.0011, 0.0015, 0.002]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should still calculate correctly with small values
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 1.0)

    def test_large_price_values(self):
        """Test with very large price values."""
        prices = [100000, 102000, 99000, 105000, 110000]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should still calculate correctly with large values
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 1.0)

    # ==========================================================
    # Error Handling Tests
    # ==========================================================

    def test_missing_close_column_raises_exception(self):
        """Test that missing Close column raises OperationalException."""
        data = {
            'DateTime': [datetime(2021, 1, 1), datetime(2021, 1, 2)],
            'Price': [100, 110]  # Wrong column name
        }
        df = pd.DataFrame(data)
        df.set_index('DateTime', inplace=True)

        with self.assertRaises(OperationalException) as context:
            get_price_efficiency_ratio(df)

        self.assertIn("Close column not found", str(context.exception))

    def test_non_datetime_index_raises_exception(self):
        """Test that non-datetime index raises OperationalException."""
        data = {
            'Index': [1, 2, 3, 4, 5],
            'Close': [100, 102, 99, 105, 110]
        }
        df = pd.DataFrame(data)
        df.set_index('Index', inplace=True)

        with self.assertRaises(OperationalException) as context:
            get_price_efficiency_ratio(df)

        self.assertIn("not a datetime", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=['Close'])
        df.index = pd.DatetimeIndex([])

        # Should handle empty DataFrame gracefully or raise appropriate error
        try:
            result = get_price_efficiency_ratio(df)
            # If it doesn't raise, result should be NaN or 0
            self.assertTrue(pd.isna(result) or result == 0.0)
        except (IndexError, ZeroDivisionError, OperationalException):
            # These exceptions are acceptable for empty data
            pass

    # ==========================================================
    # Market Scenario Tests
    # ==========================================================

    def test_bull_market_with_pullbacks(self):
        """Test bull market scenario with occasional pullbacks."""
        # Uptrend with some pullbacks
        prices = [100, 105, 103, 110, 108, 115, 112, 120]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should have moderate to high efficiency
        self.assertGreater(result, 0.5)
        self.assertLessEqual(result, 1.0)

    def test_bear_market_with_rallies(self):
        """Test bear market scenario with occasional rallies."""
        # Downtrend with some rallies
        prices = [100, 95, 98, 90, 93, 85, 88, 80]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should have moderate to high efficiency
        self.assertGreater(result, 0.5)
        self.assertLessEqual(result, 1.0)

    def test_sideways_market(self):
        """Test sideways/ranging market scenario."""
        # Price oscillates around 100
        prices = [100, 102, 98, 101, 99, 103, 97, 100]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should have very low efficiency (lots of movement, no net progress)
        self.assertLess(result, 0.2)

    def test_crash_and_recovery(self):
        """Test market crash followed by recovery."""
        prices = [100, 95, 80, 70, 65, 70, 80, 90, 100]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Price returns to start, so net change is 0
        self.assertEqual(result, 0.0)

    def test_gradual_uptrend(self):
        """Test gradual consistent uptrend."""
        # 1% daily increase
        prices = [100 * (1.01 ** i) for i in range(30)]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should have perfect or near-perfect efficiency
        self.assertGreater(result, 0.95)

    def test_gradual_downtrend(self):
        """Test gradual consistent downtrend."""
        # 1% daily decrease
        prices = [100 * (0.99 ** i) for i in range(30)]
        df = self._create_dataframe(prices)

        result = get_price_efficiency_ratio(df)

        # Should have perfect or near-perfect efficiency
        self.assertGreater(result, 0.95)

    # ==========================================================
    # Interpretation Tests
    # ==========================================================

    def test_efficiency_ratio_range(self):
        """Test that efficiency ratio is always between 0 and 1."""
        # Various scenarios
        test_cases = [
            [100, 110],  # Simple up
            [100, 90],   # Simple down
            [100, 120, 80, 110],  # Volatile
            [100, 102, 104, 106, 108, 110],  # Smooth up
            [100, 110, 105, 115, 110, 120],  # Up with pullbacks
        ]

        for prices in test_cases:
            df = self._create_dataframe(prices)
            result = get_price_efficiency_ratio(df)

            self.assertGreaterEqual(result, 0.0,
                f"Efficiency should be >= 0 for {prices}")
            self.assertLessEqual(result, 1.0,
                f"Efficiency should be <= 1 for {prices}")

    def test_higher_efficiency_means_smoother_trend(self):
        """
        Verify that smoother price paths have higher efficiency ratios.
        """
        # Smooth uptrend
        smooth_prices = [100, 102, 104, 106, 108, 110]
        smooth_df = self._create_dataframe(smooth_prices)
        smooth_efficiency = get_price_efficiency_ratio(smooth_df)

        # Volatile path to same end point
        volatile_prices = [100, 115, 95, 120, 90, 110]
        volatile_df = self._create_dataframe(volatile_prices)
        volatile_efficiency = get_price_efficiency_ratio(volatile_df)

        # Smooth path should have higher efficiency
        self.assertGreater(smooth_efficiency, volatile_efficiency)

    # ==========================================================
    # Real-world Data Pattern Tests
    # ==========================================================

    def test_intraday_pattern(self):
        """Test with intraday-like price pattern."""
        # Simulates hourly prices over a trading day
        prices = [
            100.0, 100.5, 101.0, 100.8, 101.2, 101.5, 101.3,
            102.0, 101.8, 102.2, 102.5, 102.3, 103.0
        ]
        start_date = datetime(2021, 1, 1, 9, 0, 0)
        dates = [start_date + timedelta(hours=i) for i in range(len(prices))]
        df = pd.DataFrame({'Close': prices}, index=pd.DatetimeIndex(dates))

        result = get_price_efficiency_ratio(df)

        # Should calculate correctly for intraday data
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 1.0)

    def test_weekly_data(self):
        """Test with weekly price data."""
        prices = [100, 105, 103, 110, 108, 115, 120, 118, 125, 130]
        start_date = datetime(2021, 1, 1)
        dates = [start_date + timedelta(weeks=i) for i in range(len(prices))]
        df = pd.DataFrame({'Close': prices}, index=pd.DatetimeIndex(dates))

        result = get_price_efficiency_ratio(df)

        # Should calculate correctly for weekly data
        self.assertGreater(result, 0.5)
        self.assertLessEqual(result, 1.0)
