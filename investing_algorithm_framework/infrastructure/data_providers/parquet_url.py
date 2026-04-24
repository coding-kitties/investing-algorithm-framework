from io import BytesIO

import polars as pl

from .base_url import BaseURLDataProvider


class ParquetURLDataProvider(BaseURLDataProvider):
    """
    Data provider that fetches Parquet data from a remote URL.

    Supports caching, configurable date parsing, and pre/post
    processing callbacks for data transformation.

    This provider is automatically used when a DataSource is created
    via ``DataSource.from_parquet()``.

    Note: Pre-processing callbacks are not applied for Parquet data
    since Parquet is a binary format.
    """
    data_provider_identifier = "parquet_url_data_provider"

    def _parse_raw_data(self, raw_bytes):
        """Parse raw Parquet bytes into a Polars DataFrame."""
        return pl.read_parquet(BytesIO(raw_bytes))

    def _read_cache_file(self, path):
        """Read a cached Parquet file."""
        return pl.read_parquet(path)

    def _write_cache_file(self, df, path):
        """Write a DataFrame to a Parquet cache file."""
        df.write_parquet(path)

    def _cache_file_suffix(self):
        return ".parquet"
