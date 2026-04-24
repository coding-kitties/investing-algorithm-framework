import json

import polars as pl

from .base_url import BaseURLDataProvider


class JSONURLDataProvider(BaseURLDataProvider):
    """
    Data provider that fetches JSON data from a remote URL.

    Supports caching, configurable date parsing, and pre/post
    processing callbacks for data transformation.

    This provider is automatically used when a DataSource is created
    via ``DataSource.from_json()``.

    The JSON data must be either:
    - An array of objects (records orientation), or
    - An object of arrays (columnar orientation).
    """
    data_provider_identifier = "json_url_data_provider"

    def _parse_raw_data(self, raw_bytes):
        """Parse raw JSON bytes into a Polars DataFrame."""
        text = raw_bytes.decode("utf-8")
        data = json.loads(text)

        # Handle both list-of-dicts and dict-of-lists
        if isinstance(data, list):
            return pl.DataFrame(data)
        elif isinstance(data, dict):
            return pl.DataFrame(data)
        else:
            raise ValueError(
                "JSON data must be an array of objects or an "
                "object of arrays."
            )

    def _read_cache_file(self, path):
        """Read a cached JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return pl.DataFrame(data)

    def _write_cache_file(self, df, path):
        """Write a DataFrame to a JSON cache file."""
        records = df.to_dicts()
        with open(path, "w") as f:
            json.dump(records, f)

    def _cache_file_suffix(self):
        return ".json"
