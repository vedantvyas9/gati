"""Timezone utility functions for handling UTC to local timezone conversions."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os


def get_local_timezone() -> ZoneInfo:
    """Get the configured local timezone, defaulting to system timezone."""
    # Try to get timezone from environment variable
    tz_name = os.getenv("TZ", "UTC")

    try:
        return ZoneInfo(tz_name)
    except Exception:
        # Fall back to UTC if timezone is invalid
        return ZoneInfo("UTC")


def utc_to_local(dt: datetime) -> datetime:
    """
    Convert a UTC datetime to local timezone.

    Args:
        dt: A datetime object (assumed to be UTC if naive)

    Returns:
        datetime: Datetime converted to local timezone
    """
    if dt is None:
        return None

    # If datetime is naive (no timezone info), assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to local timezone
    local_tz = get_local_timezone()
    return dt.astimezone(local_tz)


def format_datetime_local(dt: datetime) -> str:
    """
    Format a datetime as ISO 8601 string in local timezone.

    Args:
        dt: A datetime object (assumed to be UTC if naive)

    Returns:
        str: ISO 8601 formatted string in local timezone
    """
    if dt is None:
        return None

    local_dt = utc_to_local(dt)
    return local_dt.isoformat()


def parse_datetime_to_utc(dt_string: str) -> datetime:
    """
    Parse an ISO 8601 datetime string and convert to UTC.

    Args:
        dt_string: ISO 8601 formatted datetime string

    Returns:
        datetime: Datetime in UTC
    """
    if not dt_string:
        return None

    # Parse the datetime string
    dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))

    # Convert to UTC
    if dt.tzinfo is None:
        # Assume local timezone if no timezone info
        local_tz = get_local_timezone()
        dt = dt.replace(tzinfo=local_tz)

    return dt.astimezone(timezone.utc)
