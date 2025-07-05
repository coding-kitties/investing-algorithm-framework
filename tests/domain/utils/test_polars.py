from unittest import TestCase
from polars import DataFrame
from pandas import Timestamp
from investing_algorithm_framework import convert_polars_to_pandas

class TestConvertPandasToPolars(TestCase):
    
    def test_convert_pandas_to_polars(self):
        polars_df = DataFrame({
            "Datetime": ["2021-01-01", "2021-01-02", "2021-01-03"],
            "Close": [1, 2, 3]
        })

        polars_df_converted = convert_polars_to_pandas(polars_df, add_index=False)
        self.assertEqual(polars_df_converted.shape, (3, 2))

        # Check if the columns are as expected
        column_names = polars_df_converted.columns.tolist()
        self.assertEqual(set(column_names), {'Close', 'Datetime'})

        # Check if the index is a datetime object
        self.assertEqual(
            polars_df_converted['Datetime'][0], Timestamp('2021-01-01 00:00:00')
        )

        polars_df_converted = convert_polars_to_pandas(
            polars_df, add_index=True
        )
        self.assertEqual(polars_df_converted.shape, (3, 1))

        # Check if the columns are as expected
        column_names = polars_df_converted.columns.tolist()
        self.assertEqual(set(column_names), {'Close'})

        # Check if the index is a datetime object
        self.assertEqual(polars_df_converted.index.dtype, "datetime64[ns]")
        self.assertEqual(
            polars_df_converted.index[0], Timestamp('2021-01-01 00:00:00')
        )
