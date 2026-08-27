import logging
from datetime import datetime, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("investing_algorithm_framework")
_warned_unknown_timezones = set()


def format_datetime_utc(
    dt: datetime, fmt: str, tz_name: Optional[str] = None
) -> str:
    """
    Format a UTC datetime for logging/display, optionally converted to
    ``tz_name`` (an IANA zone, e.g. ``"Europe/Amsterdam"``) first — this
    is the app's configurable ``TIMEZONE`` setting.

    Applies ``fmt`` via ``dt.strftime()`` and appends a trailing zone
    marker (the resolved zone's abbreviation, e.g. ``"CEST"``, or
    ``"UTC"`` when ``tz_name`` is not set), unless ``fmt`` already
    embeds timezone info itself (``%z``/``%Z``).

    If ``tz_name`` can't be resolved (e.g. no system IANA tz database
    and the optional ``tzdata`` package isn't installed), falls back to
    ``dt`` as-is and warns once per unknown zone, rather than raising.
    """
    local_dt = dt
    if tz_name:
        try:
            local_dt = dt.astimezone(ZoneInfo(tz_name))
        except ZoneInfoNotFoundError:
            if tz_name not in _warned_unknown_timezones:
                _warned_unknown_timezones.add(tz_name)
                logger.warning(
                    f"Unknown TIMEZONE '{tz_name}' (is the 'tzdata' "
                    "package installed?) — falling back to UTC."
                )

    formatted = local_dt.strftime(fmt)
    if "%z" in fmt or "%Z" in fmt:
        return formatted
    return f"{formatted} {local_dt.tzname() or 'UTC'}"


def is_timezone_aware(dt: datetime) -> bool:
    """
    Check if a datetime object is timezone-aware.

    Args:
        dt (datetime): The datetime object to check.

    Returns:
        bool: True if the datetime is timezone-aware, False otherwise.
    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def get_timezone(dt: datetime) -> Optional[tzinfo]:
    """
    Returns the timezone info from a datetime object.

    Args:
        dt (datetime): The datetime object to check.

    Returns:
        tzinfo if available, otherwise None.
    """
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt.tzinfo
    return None


def sync_timezones(reference_dt: datetime, naive_dt: datetime) -> datetime:
    """
    Synchronize a naive datetime with the timezone of a reference datetime.

    Args:
        reference_dt (datetime): A timezone-aware datetime to
            use as a reference.
        naive_dt (datetime): A naive datetime to be synchronized.

    Returns:
        Datetime: A timezone-aware datetime that matches the
            timezone of the reference.
    """
    tz = get_timezone(reference_dt)

    if tz is None:
        return naive_dt

    # Check if tz has a localize method (pytz)
    if hasattr(tz, 'localize'):
        return tz.localize(naive_dt)
    else:
        # fallback (e.g., zoneinfo or other)
        return naive_dt.replace(tzinfo=tz)
