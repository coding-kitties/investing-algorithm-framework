from datetime import datetime
from typing import Optional
import pytz


def is_timezone_aware(dt: datetime) -> bool:
    """
    Check if a datetime object is timezone-aware.

    Args:
        dt (datetime): The datetime object to check.

    Returns:
        bool: True if the datetime is timezone-aware, False otherwise.
    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def get_timezone(dt: datetime) -> Optional[pytz.tzinfo.BaseTzInfo]:
    """
    Returns the timezone info from a datetime object.

    Args:
        dt (datetime): The datetime object to check.

    Returns:
        pytz timezone info if available, otherwise None.
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
