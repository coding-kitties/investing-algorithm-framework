from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timezone
from itertools import product
import pandas as pd
import polars as pl
from polars import DataFrame
from pandas import Timestamp
from investing_algorithm_framework import convert_polars_to_pandas


class TestConvertPandasToPolars(TestCase):

    def test_conversion_matches_previous_pipeline_exactly(self):
        dates = [datetime(2023, 1, 1, tzinfo=timezone.utc),
                 datetime(2023, 1, 1, tzinfo=timezone.utc), None,
                 datetime(2023, 1, 2, tzinfo=timezone.utc)]
        frames = [
            pl.DataFrame({'Datetime': dates, 'Close': [1.0, None, 3.0, 4.0]}),
            pl.DataFrame({'Datetime': ['2023-01-01', '2023-01-01', None],
                          'Close': [1, 2, 3]}),
            pl.DataFrame({'Close': [1, 2, 3]}),
        ]
        frames.extend(
            frames[0].with_columns(pl.col('Datetime').cast(pl.Datetime(unit)))
            for unit in ('ns', 'us', 'ms')
        )
        frames.append(frames[0].head(0))
        frames.append(frames[0].unique('Datetime', maintain_order=True))
        for frame, indexed, deduplicate in product(
                frames, (False, True), (False, True)):
            with self.subTest(schema=frame.schema, indexed=indexed,
                              deduplicate=deduplicate):
                expected = frame.to_pandas().copy()
                if 'Datetime' not in expected:
                    expected['Datetime'] = pd.to_datetime(expected.index)
                expected['Datetime'] = pd.to_datetime(expected['Datetime'])
                if deduplicate:
                    expected = expected.drop_duplicates('Datetime',
                                                        keep='first')
                if indexed:
                    expected.set_index('Datetime', inplace=True)
                actual = convert_polars_to_pandas(
                    frame, add_index=indexed, remove_duplicates=deduplicate)
                pd.testing.assert_frame_equal(actual, expected,
                                              check_exact=True)
                if not actual.empty:
                    actual.iloc[0, actual.columns.get_loc('Close')] = 99
                    self.assertEqual(frame['Close'][0], 1)

    def test_unique_indexed_dates_do_not_copy_for_deduplication(self):
        frame = pl.DataFrame({
            'Datetime': [datetime(2023, 1, 1, tzinfo=timezone.utc), None],
            'Close': [1.0, 2.0],
        })
        with patch.object(pd.DataFrame, 'drop_duplicates',
                          side_effect=AssertionError('Redundant copy')):
            actual = convert_polars_to_pandas(frame)
        actual.iloc[0, 0] = 99.0
        self.assertEqual(frame['Close'][0], 1.0)

    def test_large_frames_preserve_threaded_conversion(self):
        for size in (10_000, 10_001):
            with self.subTest(size=size):
                frame = pl.DataFrame({
                    'Datetime': pl.Series(range(size)).cast(pl.Datetime('us')),
                    'Close': range(size),
                })
                expected = frame.to_pandas().drop_duplicates('Datetime')
                expected.set_index('Datetime', inplace=True)
                original = pl.DataFrame.to_pandas
                with patch.object(pl.DataFrame, 'to_pandas', autospec=True,
                                  side_effect=original) as convert:
                    actual = convert_polars_to_pandas(frame)
                self.assertEqual(convert.call_args.kwargs,
                                 {'use_threads': size > 10_000})
                pd.testing.assert_frame_equal(actual, expected,
                                              check_exact=True)

    def test_native_datetime_column_does_not_reparse(self):
        frame = pl.DataFrame({
            'Datetime': [datetime(2023, 1, 1, tzinfo=timezone.utc)],
            'Close': [1.0],
        })
        with patch.object(pd, 'to_datetime', side_effect=AssertionError(
                'Native datetime columns do not need parsing')):
            self.assertEqual(convert_polars_to_pandas(frame).iloc[0, 0], 1.0)

    def test_convert_pandas_to_polars(self):
        polars_df = DataFrame({
            "Datetime": ["2021-01-01", "2021-01-02", "2021-01-03"],
            "Close": [1, 2, 3]
        })

        polars_df_converted = convert_polars_to_pandas(
            polars_df, add_index=False)
        self.assertEqual(polars_df_converted.shape, (3, 2))

        # Check if the columns are as expected
        column_names = polars_df_converted.columns.tolist()
        self.assertEqual(set(column_names), {'Close', 'Datetime'})

        # Check if the index is a datetime object
        self.assertEqual(
            polars_df_converted['Datetime'][0],
            Timestamp('2021-01-01 00:00:00')
        )

        polars_df_converted = convert_polars_to_pandas(
            polars_df, add_index=True
        )
        self.assertEqual(polars_df_converted.shape, (3, 1))

        # Check if the columns are as expected
        column_names = polars_df_converted.columns.tolist()
        self.assertEqual(set(column_names), {'Close'})

        # Check if the index is a datetime object
        self.assertTrue(
            str(polars_df_converted.index.dtype).startswith("datetime64")
        )
        self.assertEqual(
            polars_df_converted.index[0], Timestamp('2021-01-01 00:00:00')
        )
