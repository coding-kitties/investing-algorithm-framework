from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Optional


def _enum_value(value):
    return getattr(value, "value", value)


def _callable_identifier(value):
    if value is None:
        return None
    return (
        getattr(value, "__module__", type(value).__module__),
        getattr(value, "__qualname__", type(value).__qualname__),
    )


def _secret_fingerprint(value) -> Optional[str]:
    if not value:
        return None
    payload = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return sha256(payload).hexdigest()


def _data_source_key(data_source) -> tuple:
    return (
        data_source.data_provider_identifier,
        _enum_value(data_source.data_type),
        data_source.symbol,
        data_source.market,
        _enum_value(data_source.time_frame),
        data_source.warmup_window,
        data_source.storage_path,
        data_source.pandas,
        data_source.date,
        data_source.start_date,
        data_source.end_date,
        data_source.save,
        data_source.url,
        data_source.date_column,
        data_source.date_format,
        data_source.cache,
        data_source.refresh_interval,
        _secret_fingerprint(data_source.headers),
        _callable_identifier(data_source.pre_process),
        _callable_identifier(data_source.post_process),
    )


def _provider_catalog_key(providers) -> tuple:
    catalog = (
        (
            type(provider).__module__,
            type(provider).__qualname__,
            provider.data_provider_identifier,
            provider.priority,
            getattr(provider, "storage_path", None),
            getattr(provider, "storage_directory", None),
            bool(getattr(provider, "pandas", False)),
        )
        for provider in providers
    )
    return tuple(sorted(catalog, key=repr))


def _estimate_size(value: Any) -> int:
    if value is None:
        return 0
    estimated_size = getattr(value, "estimated_size", None)
    if callable(estimated_size):
        return int(estimated_size())
    memory_usage = getattr(value, "memory_usage", None)
    if callable(memory_usage):
        usage = memory_usage(index=True, deep=True)
        return int(usage.sum() if hasattr(usage, "sum") else usage)
    try:
        return int(value.nbytes)
    except (AttributeError, TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class PreparedMarketDataStats:
    hits: int
    misses: int
    builds: int
    evictions: int
    admission_rejections: int
    resident_bytes: int
    entries: int
    registration_seconds: float
    preparation_seconds: float
    rolling_cache_builds: int


class PreparedMarketDataContext:
    """Bounded optimization-scoped cache of prepared provider payloads."""

    def __init__(self, max_bytes: int):
        if isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer.")
        self.max_bytes = int(max_bytes)
        self._entries = OrderedDict()
        self._resident_bytes = 0
        self._hits = 0
        self._misses = 0
        self._builds = 0
        self._evictions = 0
        self._admission_rejections = 0
        self._registration_seconds = 0.0
        self._preparation_seconds = 0.0
        self._rolling_cache_builds = 0

    @staticmethod
    def key(
        data_source,
        backtest_date_range,
        providers,
        *,
        access_pattern: str,
        fill_missing_data: bool,
        save_filled_data_points: bool,
    ) -> tuple:
        return (
            _data_source_key(data_source),
            backtest_date_range.start_date,
            backtest_date_range.end_date,
            _provider_catalog_key(providers),
            access_pattern,
            bool(fill_missing_data),
            bool(save_filled_data_points),
        )

    def get(self, key):
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        self._entries.move_to_end(key)
        self._hits += 1
        return entry[0]

    def put(self, key, provider) -> bool:
        self._builds += 1
        size = _estimate_size(getattr(provider, "data", None))
        size += sum(
            _estimate_size(value)
            for value in getattr(provider, "window_cache", {}).values()
        )
        if size > self.max_bytes:
            self._admission_rejections += 1
            return False

        previous = self._entries.pop(key, None)
        if previous is not None:
            self._resident_bytes -= previous[1]
        while self._entries and self._resident_bytes + size > self.max_bytes:
            _, (_, evicted_size) = self._entries.popitem(last=False)
            self._resident_bytes -= evicted_size
            self._evictions += 1
        self._entries[key] = (provider, size)
        self._resident_bytes += size
        return True

    def record_registration(self, seconds: float) -> None:
        self._registration_seconds += seconds

    def record_preparation(
        self, seconds: float, *, rolling_cache_built: bool
    ) -> None:
        self._preparation_seconds += seconds
        if rolling_cache_built:
            self._rolling_cache_builds += 1

    @property
    def stats(self) -> PreparedMarketDataStats:
        return PreparedMarketDataStats(
            hits=self._hits,
            misses=self._misses,
            builds=self._builds,
            evictions=self._evictions,
            admission_rejections=self._admission_rejections,
            resident_bytes=self._resident_bytes,
            entries=len(self._entries),
            registration_seconds=self._registration_seconds,
            preparation_seconds=self._preparation_seconds,
            rolling_cache_builds=self._rolling_cache_builds,
        )

    def close(self) -> None:
        self._entries.clear()
        self._resident_bytes = 0
