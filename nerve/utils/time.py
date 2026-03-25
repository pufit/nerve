"""Timezone helpers — UTC storage, local display.

Convention:
  - All database timestamps are UTC (datetime.now(timezone.utc) or CURRENT_TIMESTAMP).
  - Convert to local time only at display boundaries (CLI output, user-facing messages).
  - Use config.timezone (e.g., "America/New_York") for display conversion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Current time in UTC (for storage)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 string (for DB storage)."""
    return datetime.now(timezone.utc).isoformat()


def local_now(tz_name: str) -> datetime:
    """Current time in the configured local timezone (for logic like quiet hours)."""
    return datetime.now(ZoneInfo(tz_name))


def to_local(dt_or_iso: datetime | str, tz_name: str) -> datetime:
    """Convert a UTC datetime or ISO string to the local timezone.

    Handles both aware datetimes and naive strings from SQLite
    (assumed UTC per project convention).
    """
    if isinstance(dt_or_iso, str):
        # SQLite CURRENT_TIMESTAMP produces "YYYY-MM-DD HH:MM:SS" (space separator)
        dt = datetime.fromisoformat(dt_or_iso.replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt_or_iso
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name))


def format_local(
    dt_or_iso: datetime | str,
    tz_name: str,
    fmt: str = "%Y-%m-%d %H:%M %Z",
) -> str:
    """Format a UTC timestamp as a local time string for display."""
    return to_local(dt_or_iso, tz_name).strftime(fmt)
