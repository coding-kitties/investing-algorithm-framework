import unittest
import tempfile
import os
from datetime import datetime

import pandas as pd
import polars as pl

from investing_algorithm_framework.services.data_providers.data import (
    fill_missing_timeseries_data,
    get_missing_timeseries_data_entries
)


class TestGetMissingTimeseriesDataEntries(unittest.TestCase):
    """Tests for the get_missing_timeseries_data_entries function."""

    def test_no_missing_entries(self):
        """Test when there are no missing entries in the data."""
        dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='D')
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        missing = get_missing_timeseries_data_entries(df)

        self.assertEqual(len(missing), 0)

    def test_missing_entries_in_middle(self):
        """Test detection of missing entries in the middle of the data."""
        # Create data with a gap (missing Jan 5, 6, 7)
        dates = pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03',
                                '2024-01-04', '2024-01-08', '2024-01-09',
                                '2024-01-10'])
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        missing = get_missing_timeseries_data_entries(df, freq='D')

        self.assertEqual(len(missing), 3)
        expected_missing = [
            pd.Timestamp('2024-01-05'),
            pd.Timestamp('2024-01-06'),
            pd.Timestamp('2024-01-07')
        ]
        for expected, actual in zip(expected_missing, missing):
            self.assertEqual(expected, actual)

    def test_with_start_and_end_parameters(self):
        """Test with explicit start and end parameters."""
        dates = pd.to_datetime(['2024-01-03', '2024-01-04', '2024-01-05'])
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        # Check for missing dates from Jan 1 to Jan 7
        missing = get_missing_timeseries_data_entries(
            df,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 7),
            freq='D'
        )

        self.assertEqual(len(missing), 4)  # Jan 1, 2, 6, 7 are missing

    def test_hourly_frequency(self):
        """Test with hourly frequency data."""
        dates = pd.to_datetime([
            '2024-01-01 00:00', '2024-01-01 01:00', '2024-01-01 02:00',
            '2024-01-01 05:00', '2024-01-01 06:00'
        ])
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        missing = get_missing_timeseries_data_entries(df, freq='H')

        self.assertEqual(len(missing), 2)  # 03:00 and 04:00 are missing

    def test_with_csv_file(self):
        """Test loading data from a CSV file."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-05'])
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as f:
            df.to_csv(f.name)
            temp_path = f.name

        try:
            missing = get_missing_timeseries_data_entries(temp_path, freq='D')
            self.assertEqual(len(missing), 2)  # Jan 3 and 4 are missing
        finally:
            os.unlink(temp_path)

    def test_with_polars_dataframe(self):
        """Test with polars DataFrame input."""
        dates = ['2024-01-01', '2024-01-02', '2024-01-05']
        df = pl.DataFrame({
            'Datetime': pd.to_datetime(dates),
            'value': [1, 2, 3]
        })

        missing = get_missing_timeseries_data_entries(df, freq='D')

        self.assertEqual(len(missing), 2)  # Jan 3 and 4 are missing

    def test_inferred_frequency(self):
        """Test that frequency is correctly inferred from data."""
        # 2-hour frequency data
        dates = pd.to_datetime([
            '2024-01-01 00:00', '2024-01-01 02:00', '2024-01-01 04:00',
            '2024-01-01 08:00', '2024-01-01 10:00'
        ])
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        missing = get_missing_timeseries_data_entries(df)

        # Should detect 06:00 as missing (2-hour frequency)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0], pd.Timestamp('2024-01-01 06:00'))

    def test_empty_dataframe(self):
        """Test with an empty DataFrame."""
        df = pd.DataFrame({'value': []})
        df.index = pd.to_datetime([])
        df.index.name = 'Datetime'

        # Should handle empty data gracefully
        missing = get_missing_timeseries_data_entries(
            df,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 5),
            freq='D'
        )

        self.assertEqual(len(missing), 5)


class TestFillMissingTimeseriesData(unittest.TestCase):
    """Tests for the fill_missing_timeseries_data function."""

    def test_forward_fill_missing_dates(self):
        """Test that missing dates are forward-filled."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-05'])
        df = pd.DataFrame({
            'Open': [100, 101, 104],
            'High': [105, 106, 109],
            'Low': [95, 96, 99],
            'Close': [102, 103, 106],
            'Volume': [1000, 1100, 1400]
        }, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(
            df,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5)
        )

        self.assertEqual(len(result), 5)
        # Check that Jan 3 and 4 are filled with Jan 2 values (forward fill)
        self.assertEqual(result.loc[pd.Timestamp('2024-01-03'), 'Close'], 103)
        self.assertEqual(result.loc[pd.Timestamp('2024-01-04'), 'Close'], 103)

    def test_backward_fill_at_start(self):
        """Test that missing dates at the start are backward-filled."""
        dates = pd.to_datetime(['2024-01-03', '2024-01-04', '2024-01-05'])
        df = pd.DataFrame({
            'Open': [102, 103, 104],
            'Close': [103, 104, 105]
        }, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(
            df,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5)
        )

        self.assertEqual(len(result), 5)
        # Check that Jan 1 and 2 are filled with Jan 3 values (backward fill)
        self.assertEqual(result.loc[pd.Timestamp('2024-01-01'), 'Close'], 103)
        self.assertEqual(result.loc[pd.Timestamp('2024-01-02'), 'Close'], 103)

    def test_with_explicit_missing_dates(self):
        """Test filling specific missing dates."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-05'])
        df = pd.DataFrame({
            'value': [100, 104]
        }, index=dates)
        df.index.name = 'Datetime'

        missing_dates = [
            datetime(2024, 1, 2),
            datetime(2024, 1, 3)
        ]

        result = fill_missing_timeseries_data(df, missing_dates=missing_dates)

        self.assertEqual(len(result), 4)
        # Forward filled from Jan 1
        self.assertEqual(result.loc[pd.Timestamp('2024-01-02'), 'value'], 100)
        self.assertEqual(result.loc[pd.Timestamp('2024-01-03'), 'value'], 100)

    def test_no_missing_dates(self):
        """Test when there are no missing dates."""
        dates = pd.date_range(start='2024-01-01', end='2024-01-05', freq='D')
        df = pd.DataFrame({'value': range(len(dates))}, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(
            df,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5)
        )

        self.assertEqual(len(result), 5)
        pd.testing.assert_frame_equal(result, df)

    def test_with_csv_file(self):
        """Test loading and saving to CSV file."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-05'])
        df = pd.DataFrame({'value': [100, 101, 104]}, index=dates)
        df.index.name = 'Datetime'

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as f:
            df.to_csv(f.name)
            temp_path = f.name

        try:
            result = fill_missing_timeseries_data(
                temp_path,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 5)
            )

            self.assertEqual(len(result), 5)
        finally:
            os.unlink(temp_path)

    def test_save_to_file(self):
        """Test saving filled data back to file."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-05'])
        df = pd.DataFrame({'value': [100, 104]}, index=dates)
        df.index.name = 'Datetime'

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False
        ) as f:
            df.to_csv(f.name)
            temp_path = f.name

        try:
            fill_missing_timeseries_data(
                temp_path,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 5),
                save_to_file=True
            )

            # Read back and verify
            saved_df = pd.read_csv(temp_path, index_col=0, parse_dates=True)
            self.assertEqual(len(saved_df), 5)
        finally:
            os.unlink(temp_path)

    def test_with_polars_dataframe(self):
        """Test with polars DataFrame input returns polars DataFrame."""
        dates = ['2024-01-01', '2024-01-02', '2024-01-05']
        df = pl.DataFrame({
            'Datetime': pd.to_datetime(dates),
            'value': [100, 101, 104]
        })

        result = fill_missing_timeseries_data(
            df,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5)
        )

        self.assertIsInstance(result, pl.DataFrame)
        self.assertEqual(len(result), 5)

    def test_preserves_all_columns(self):
        """Test that all columns are preserved when filling."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-03'])
        df = pd.DataFrame({
            'Open': [100, 102],
            'High': [105, 107],
            'Low': [95, 97],
            'Close': [102, 104],
            'Volume': [1000, 1200],
            'custom_col': ['a', 'b']
        }, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(
            df,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3)
        )

        self.assertEqual(len(result), 3)
        # Check all columns are present
        self.assertEqual(
            list(result.columns),
            ['Open', 'High', 'Low', 'Close', 'Volume', 'custom_col']
        )
        # Check filled row has all values from previous row
        self.assertEqual(
            result.loc[pd.Timestamp('2024-01-02'), 'custom_col'], 'a'
        )

    def test_sorted_output(self):
        """Test that output is sorted by index."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-05', '2024-01-03'])
        df = pd.DataFrame({'value': [100, 104, 102]}, index=dates)
        df.index.name = 'Datetime'

        missing_dates = [datetime(2024, 1, 2), datetime(2024, 1, 4)]

        result = fill_missing_timeseries_data(df, missing_dates=missing_dates)

        # Check output is sorted
        self.assertTrue(result.index.is_monotonic_increasing)

    def test_empty_missing_dates_list(self):
        """Test with empty missing dates list."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-02'])
        df = pd.DataFrame({'value': [100, 101]}, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(df, missing_dates=[])

        self.assertEqual(len(result), 2)
        pd.testing.assert_frame_equal(result, df)

    def test_no_parameters_returns_unchanged(self):
        """Test that without parameters, data is returned unchanged."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-05'])
        df = pd.DataFrame({'value': [100, 104]}, index=dates)
        df.index.name = 'Datetime'

        result = fill_missing_timeseries_data(df)

        self.assertEqual(len(result), 2)

    def test_duplicate_missing_dates_ignored(self):
        """Test that duplicate dates in missing_dates are handled."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-05'])
        df = pd.DataFrame({'value': [100, 104]}, index=dates)
        df.index.name = 'Datetime'

        missing_dates = [
            datetime(2024, 1, 2),
            datetime(2024, 1, 2),  # Duplicate
            datetime(2024, 1, 3)
        ]

        result = fill_missing_timeseries_data(df, missing_dates=missing_dates)

        # Should have 4 rows (not 5, duplicate should be handled)
        self.assertEqual(len(result), 4)

    def test_already_existing_date_in_missing_dates(self):
        """Test that dates already in data are not duplicated."""
        dates = pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-05'])
        df = pd.DataFrame({'value': [100, 101, 104]}, index=dates)
        df.index.name = 'Datetime'

        missing_dates = [
            datetime(2024, 1, 2),  # Already exists
            datetime(2024, 1, 3)   # Missing
        ]

        result = fill_missing_timeseries_data(df, missing_dates=missing_dates)

        self.assertEqual(len(result), 4)


if __name__ == '__main__':
    unittest.main()

