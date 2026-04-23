from io import StringIO

import polars as pl

from .base_url import BaseURLDataProvider


class CSVURLDataProvider(BaseURLDataProvider):
    """
    Data provider that fetches CSV data from a remote URL.

    Supports caching, configurable date parsing, and pre/post
    processing callbacks for data transformation.

    This provider is automatically used when a DataSource is created
    via ``DataSource.from_csv()``.
    """
    data_provider_identifier = "csv_url_data_provider"

    def _parse_raw_data(self, raw_bytes):
        """Parse raw CSV bytes into a Polars DataFrame."""
        return pl.read_csv(StringIO(raw_bytes.decode("utf-8")))

    def _read_cache_file(self, path):
        """Read a cached CSV file."""
        return pl.read_csv(path)

    def _write_cache_file(self, df, path):
        """Write a DataFrame to a CSV cache file."""
        df.write_csv(path)

    def _cache_file_suffix(self):
        return ".csv"
