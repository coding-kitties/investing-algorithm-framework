import hashlib
import logging
import os
import ssl
import time
import urllib.request
from abc import abstractmethod

import polars as pl

from investing_algorithm_framework.domain import DataProvider, DataType

logger = logging.getLogger("investing_algorithm_framework")

# Mapping of refresh_interval strings to seconds
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1W": 604800,
}


class BaseURLDataProvider(DataProvider):
    """
    Abstract base class for data providers that fetch data from a
    remote URL.

    Provides shared logic for caching, refresh intervals,
    pre/post-processing callbacks, and date parsing. Subclasses
    only need to implement ``_parse_raw_data`` and
    ``_write_cache_file`` for their specific format.
    """
    data_type = DataType.CUSTOM
    data_provider_identifier = None  # Must be set by subclasses

    def __init__(
        self,
        url=None,
        date_column=None,
        date_format=None,
        cache=True,
        refresh_interval=None,
        pre_process=None,
        post_process=None,
        priority=5,
        identifier=None,
    ):
        super().__init__(
            data_provider_identifier=(
                identifier or self.data_provider_identifier
            ),
            data_type=DataType.CUSTOM.value,
            priority=priority,
        )
        self._url = url
        self._date_column = date_column
        self._date_format = date_format
        self._cache = cache
        self._refresh_interval = refresh_interval
        self._pre_process = pre_process
        self._post_process = post_process
        self._cached_data = None
        self._last_fetch_time = None

    # ------------------------------------------------------------------
    # Abstract methods — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _parse_raw_data(self, raw_bytes):
        """
        Parse raw bytes fetched from the URL into a Polars DataFrame.

        Args:
            raw_bytes (bytes): The raw content downloaded from the URL.

        Returns:
            polars.DataFrame: Parsed tabular data.
        """
        raise NotImplementedError

    @abstractmethod
    def _read_cache_file(self, path):
        """
        Read a cached file from disk into a Polars DataFrame.

        Args:
            path (str): Path to the cache file.

        Returns:
            polars.DataFrame
        """
        raise NotImplementedError

    @abstractmethod
    def _write_cache_file(self, df, path):
        """
        Write a Polars DataFrame to disk as a cache file.

        Args:
            df (polars.DataFrame): The data to cache.
            path (str): Path to write to.
        """
        raise NotImplementedError

    @abstractmethod
    def _cache_file_suffix(self):
        """Return the file extension for cache files (e.g. '.csv')."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def has_data(self, data_source, start_date=None, end_date=None):
        """Check if this provider can serve the given data source."""
        if not DataType.CUSTOM.equals(data_source.data_type):
            return False

        if data_source.data_provider_identifier \
                == self.data_provider_identifier \
                and data_source.url is not None:
            return True

        return False

    def get_data(
        self, date=None, start_date=None, end_date=None, save=False
    ):
        """Fetch and return data from the configured URL."""
        if self._should_refetch():
            self._fetch_and_parse()

        return self._cached_data

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data=False,
        show_progress=False,
    ):
        """Pre-fetch data for backtesting."""
        self._fetch_and_parse()

    def get_backtest_data(
        self,
        backtest_index_date=None,
        backtest_start_date=None,
        backtest_end_date=None,
        data_source=None,
    ):
        """Return data for a specific backtest date."""
        if self._cached_data is None:
            self._fetch_and_parse()

        df = self._cached_data

        # Filter by date column if available
        if self._date_column and self._date_column in df.columns:
            if backtest_index_date is not None:
                try:
                    df = df.filter(
                        pl.col(self._date_column) <= backtest_index_date
                    )
                except Exception:
                    pass

        return df

    def get_number_of_data_points(self, start_date, end_date):
        """Return the number of rows in the cached data."""
        if self._cached_data is None:
            return 0
        return len(self._cached_data)

    def get_missing_data_dates(self, start_date, end_date):
        """URL-fetched data does not track missing dates."""
        return []

    def get_data_source_file_path(self):
        """Return the cache file path if available."""
        return self._get_cache_path()

    def copy(self, data_source=None):
        """Create a copy of this provider configured for a data source."""
        url = self._url
        date_column = self._date_column
        date_format = self._date_format
        cache = self._cache
        refresh_interval = self._refresh_interval
        pre_process = self._pre_process
        post_process = self._post_process
        identifier = self.data_provider_identifier

        if data_source is not None:
            url = data_source.url or url
            date_column = data_source.date_column or date_column
            date_format = data_source.date_format or date_format
            cache = data_source.cache if data_source.cache is not None \
                else cache
            refresh_interval = data_source.refresh_interval \
                or refresh_interval
            pre_process = data_source.pre_process or pre_process
            post_process = data_source.post_process or post_process

        provider = self.__class__(
            url=url,
            date_column=date_column,
            date_format=date_format,
            cache=cache,
            refresh_interval=refresh_interval,
            pre_process=pre_process,
            post_process=post_process,
            priority=self.priority,
            identifier=identifier,
        )
        provider.config = self.config
        return provider

    # ------------------------------------------------------------------
    # Shared internal helpers
    # ------------------------------------------------------------------

    def _should_refetch(self):
        """Determine if data should be re-fetched."""
        if self._cached_data is None:
            return True

        if not self._cache:
            return True

        if self._refresh_interval and self._last_fetch_time:
            interval_seconds = INTERVAL_SECONDS.get(
                self._refresh_interval, None
            )

            if interval_seconds is not None:
                elapsed = time.time() - self._last_fetch_time
                return elapsed >= interval_seconds

        return False

    def _fetch_and_parse(self):
        """Fetch data from URL, apply callbacks, and cache."""
        url = self._url

        if url is None:
            raise ValueError(
                f"{self.__class__.__name__} requires a URL. "
                f"Configure it via the appropriate DataSource "
                f"factory method."
            )

        logger.info(f"Fetching data from: {url}")

        # Check for local cache file first
        cache_path = self._get_cache_path()

        if cache_path and self._cache and os.path.exists(cache_path):
            if not self._should_refetch_from_cache(cache_path):
                logger.debug(f"Loading cached data from: {cache_path}")
                df = self._read_cache_file(cache_path)
                df = self._parse_dates(df)

                if self._post_process:
                    df = self._post_process(df)

                self._cached_data = df
                self._last_fetch_time = os.path.getmtime(cache_path)
                return

        # Fetch from URL
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "investing-algorithm-framework"}
        )
        with urllib.request.urlopen(req, context=ctx) as response:
            raw_bytes = response.read()

        # Apply pre-processing callback (operates on text)
        if self._pre_process:
            raw_text = raw_bytes.decode("utf-8")
            raw_text = self._pre_process(raw_text)
            raw_bytes = raw_text.encode("utf-8")

        # Parse into DataFrame (format-specific)
        df = self._parse_raw_data(raw_bytes)

        # Parse date column
        df = self._parse_dates(df)

        # Save to cache file
        if cache_path and self._cache:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            self._write_cache_file(df, cache_path)
            logger.debug(f"Cached data to: {cache_path}")

        # Apply post-processing callback
        if self._post_process:
            df = self._post_process(df)

        self._cached_data = df
        self._last_fetch_time = time.time()

    def _parse_dates(self, df):
        """Parse the date column if configured."""
        if self._date_column and self._date_column in df.columns:
            try:
                if self._date_format:
                    df = df.with_columns(
                        pl.col(self._date_column)
                        .str.strptime(pl.Datetime, self._date_format)
                        .alias(self._date_column)
                    )
                else:
                    df = df.with_columns(
                        pl.col(self._date_column)
                        .str.to_datetime()
                        .alias(self._date_column)
                    )
            except Exception as e:
                logger.warning(
                    f"Could not parse date column "
                    f"'{self._date_column}': {e}"
                )

        return df

    def _get_cache_path(self):
        """Generate a cache file path based on the URL hash."""
        if self._url is None:
            return None

        storage_dir = None

        if self.config:
            resource_dir = self.config.get("RESOURCE_DIRECTORY")
            data_dir_name = self.config.get("DATA_DIRECTORY")

            if resource_dir and data_dir_name:
                storage_dir = os.path.join(resource_dir, data_dir_name)

        if storage_dir is None:
            storage_dir = os.path.join(os.getcwd(), ".data_cache")

        url_hash = hashlib.md5(
            self._url.encode()
        ).hexdigest()[:12]
        suffix = self._cache_file_suffix()
        return os.path.join(storage_dir, f"url_{url_hash}{suffix}")

    def _should_refetch_from_cache(self, cache_path):
        """Check if cached file is stale based on refresh interval."""
        if not self._refresh_interval:
            return False

        interval_seconds = INTERVAL_SECONDS.get(
            self._refresh_interval, None
        )

        if interval_seconds is None:
            return False

        file_age = time.time() - os.path.getmtime(cache_path)
        return file_age >= interval_seconds
